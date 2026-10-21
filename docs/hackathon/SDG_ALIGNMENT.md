# Argus and the Sustainable Development Goals

## Primary alignment: SDG 16, Peace, Justice and Strong Institutions

Argus has an indirect, enabling relationship to **UN Sustainable Development Goal 16**, especially **Target 16.6: develop effective, accountable, and transparent institutions at all levels**. The UN describes Goal 16 as advancing peaceful and inclusive societies, access to justice, and effective, accountable, inclusive institutions. See the [official UN Goal 16 page](https://sdgs.un.org/goals/goal16).

Argus supports accountability in a narrow organizational process: employee and compensation changes are captured in a hash-linked PostgreSQL audit trail; integrity checks surface certain out-of-band edits; and auditors can inspect evidence or replay an employee history without changing the source records. This can make an internal review more traceable and give reviewers portable evidence to examine.

## Claim boundary

Argus is an audit prototype, not an institution, legal process, anti-corruption program, or SDG indicator. It does not by itself demonstrate less corruption, improved justice access, fairer pay, or measurable progress toward Target 16.6. Its contribution is limited to providing a technical control that could support accountable recordkeeping when deployed with independent key custody, trusted external checkpoints, appropriate access controls, and human review.

The local hackathon setup uses synthetic data and a local file anchor. It does not have a persisted independent witness quorum. The panel description should therefore say **“supports auditability relevant to SDG 16.6”**, not **“achieves SDG 16”** or “reduces corruption.”

## Suggested presentation wording

> “Argus is aligned with SDG 16.6 because it helps an organization make sensitive employee-record changes more traceable and independently reviewable. This is an enabling technical contribution; our prototype does not measure institutional transparency or claim direct SDG impact.”

## What would be needed to measure impact

An impact study would need a deployed organization, a defined baseline process, privacy-protective operational data, and measures such as time to detect and investigate unauthorized changes, completeness of audit evidence, and reviewer error rates. Those outcomes have not been measured by this prototype.
