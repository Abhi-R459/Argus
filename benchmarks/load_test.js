import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 20 }, // ramp up to 20 users
    { duration: '1m', target: 20 },  // stay at 20 users for 1 minute
    { duration: '30s', target: 0 },  // ramp down to 0 users
  ],
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';

export default function () {
  const res = http.get(`${BASE_URL}/api/health`);
  check(res, {
    'is status 200': (r) => r.status === 200,
    'verify status message': (r) => {
      try {
        return r.json('status') === 'ok';
      } catch (e) {
        return false;
      }
    }
  });
  sleep(1);
}
