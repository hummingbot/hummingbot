import request from 'supertest';
import { gatewayApp } from '../../src/app';

describe('GET /connectors', () => {
  it('should return 200 with a list of connectors', async () => {
    await request(gatewayApp)
      .get(`/connectors`)
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.connectors).toBeDefined());
  });
});
