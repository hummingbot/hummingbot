import { app } from '../src/app';
import request from 'supertest';

describe('GET /', () => {
  it('should return 200', async () => {
    request(app)
      .get(`/`)
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.status).toBe('ok'));
  });
});
