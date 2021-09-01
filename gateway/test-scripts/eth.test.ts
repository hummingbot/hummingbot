import request from 'supertest';
import { app } from '../src/app';

describe('Eth endpoints', () => {
  it('should get a 200 OK on /', async () => {
    const res = await request(app)
      .get('/')
    expect(res.statusCode).toEqual(200);
  })
})
