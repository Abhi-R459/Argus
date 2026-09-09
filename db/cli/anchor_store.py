"""Pluggable external anchor store for Argus checkpoint tamper evidence."""

import abc
import base64
import json
from pathlib import Path
import urllib.request
import urllib.error
from typing import Dict, Any

class AnchorStore(abc.ABC):
    """Abstract base class for anchor stores."""

    @abc.abstractmethod
    def push(self, checkpoint_id: int, payload_json: str) -> str:
        """Pushes a checkpoint to the anchor store.

        Args:
            checkpoint_id (int): The ID of the checkpoint.
            payload_json (str): The JSON payload containing checkpoint data.

        Returns:
            str: A reference string for the stored anchor.
        """
        pass

    @abc.abstractmethod
    def verify(self, checkpoint_id: int) -> bool:
        """Verifies that a checkpoint exists and is valid in the anchor store.

        Args:
            checkpoint_id (int): The ID of the checkpoint to verify.

        Returns:
            bool: True if the checkpoint is valid, False otherwise.
        """
        pass


class LocalFileAnchorStore(AnchorStore):
    """Local file system implementation of an anchor store."""

    def __init__(self, base_path: str):
        """Initializes the LocalFileAnchorStore.

        Args:
            base_path (str): The base directory for anchor files.
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def push(self, checkpoint_id: int, payload_json: str) -> str:
        """Pushes a checkpoint to a local file.

        Args:
            checkpoint_id (int): The ID of the checkpoint.
            payload_json (str): The JSON payload containing checkpoint data.

        Returns:
            str: The file path where the anchor was saved.
        """
        file_path = self.base_path / f"{checkpoint_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(payload_json)
        return str(file_path)

    def verify(self, checkpoint_id: int) -> bool:
        """Verifies a checkpoint in the local file system.

        Args:
            checkpoint_id (int): The ID of the checkpoint to verify.

        Returns:
            bool: True if the checkpoint file exists and contains valid JSON.
        """
        file_path = self.base_path / f"{checkpoint_id}.json"
        if not file_path.exists():
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                json.loads(content)
            return True
        except (json.JSONDecodeError, OSError):
            return False


class GitHubAnchorStore(AnchorStore):
    """GitHub implementation of an anchor store."""

    def __init__(self, repo: str, token: str, branch: str = 'main', path_prefix: str = 'anchors'):
        """Initializes the GitHubAnchorStore.

        Args:
            repo (str): The GitHub repository in the format "owner/repo".
            token (str): A GitHub Personal Access Token for authentication.
            branch (str, optional): The branch to commit to. Defaults to 'main'.
            path_prefix (str, optional): The path prefix within the repo. Defaults to 'anchors'.
        """
        self.repo = repo
        self.token = token
        self.branch = branch
        self.path_prefix = path_prefix
        self.base_url = f"https://api.github.com/repos/{self.repo}/contents"

    def _get_headers(self) -> Dict[str, str]:
        """Returns the headers required for GitHub API requests.

        Returns:
            Dict[str, str]: A dictionary of HTTP headers.
        """
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Argus-Anchor-Store"
        }

    def push(self, checkpoint_id: int, payload_json: str) -> str:
        """Pushes a checkpoint to GitHub.

        Args:
            checkpoint_id (int): The ID of the checkpoint.
            payload_json (str): The JSON payload containing checkpoint data.

        Returns:
            str: The GitHub API URL for the created file.
            
        Raises:
            Exception: If the GitHub API request fails.
        """
        path = f"{self.path_prefix}/{checkpoint_id}.json".strip('/')
        url = f"{self.base_url}/{path}"
        
        # Check if file exists to get sha for updating (though checkpoints should be immutable)
        sha = None
        try:
            req = urllib.request.Request(url, headers=self._get_headers())
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                sha = data.get('sha')
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise

        content_b64 = base64.b64encode(payload_json.encode("utf-8")).decode("utf-8")
        
        body: Dict[str, Any] = {
            "message": f"Anchor checkpoint {checkpoint_id}",
            "content": content_b64,
            "branch": self.branch
        }
        if sha:
            body["sha"] = sha

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=self._get_headers(),
            method="PUT"
        )

        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result['content']['html_url']
        except urllib.error.URLError as e:
            raise Exception(f"Failed to push anchor to GitHub: {e}")

    def verify(self, checkpoint_id: int) -> bool:
        """Verifies a checkpoint in GitHub.

        Args:
            checkpoint_id (int): The ID of the checkpoint to verify.

        Returns:
            bool: True if the checkpoint exists and is valid JSON, False otherwise.
        """
        path = f"{self.path_prefix}/{checkpoint_id}.json".strip('/')
        url = f"{self.base_url}/{path}?ref={self.branch}"

        req = urllib.request.Request(url, headers=self._get_headers())

        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                content_b64 = data.get("content", "")
                
                # Check for empty content which might happen
                if not content_b64:
                    return False
                    
                content_json = base64.b64decode(content_b64).decode("utf-8")
                
                # Ensure it's valid JSON
                json.loads(content_json)
                return True
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
            return False


def get_anchor_store(config: dict) -> AnchorStore:
    """Factory function to get the appropriate anchor store based on configuration.

    Args:
        config (dict): Configuration dictionary. Must contain a 'type' key 
                       ('local' or 'github') and required parameters for that type.

    Returns:
        AnchorStore: An instance of the configured anchor store.
        
    Raises:
        ValueError: If the anchor store type is unknown or configuration is invalid.
    """
    store_type = config.get("type")
    
    if store_type == "local":
        base_path = config.get("path") or config.get("base_path")
        if not base_path:
            raise ValueError("LocalFileAnchorStore requires 'path' or 'base_path' in config.")
        return LocalFileAnchorStore(base_path=base_path)
        
    elif store_type == "github":
        repo = config.get("repo")
        token = config.get("token")
        
        if not repo or not token:
            raise ValueError("GitHubAnchorStore requires 'repo' and 'token' in config.")
            
        kwargs = {"repo": repo, "token": token}
        
        if "branch" in config:
            kwargs["branch"] = config["branch"]
        if "path_prefix" in config:
            kwargs["path_prefix"] = config["path_prefix"]
            
        return GitHubAnchorStore(**kwargs)
        
    else:
        raise ValueError(f"Unknown anchor store type: {store_type}")
