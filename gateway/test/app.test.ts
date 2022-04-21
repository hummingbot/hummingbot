jest.useFakeTimers();
import { gatewayApp, swaggerDocument } from '../src/app';
import { difference } from 'lodash';

describe('verify swagger docs', () => {
  it('All routes should have swagger documentation', () => {
    const documentedRoutes = Object.keys(swaggerDocument.paths).sort();

    const allRoutes: any[] = [];
    gatewayApp._router.stack.forEach(function (middleware: any) {
      if (middleware.route) {
        // routes registered directly on the gatewayApp
        allRoutes.push(middleware.route.path);
      } else if (middleware.name === 'router') {
        const parentPath = middleware.regexp
          .toString()
          .split('?')[0]
          .slice(2)
          .replaceAll('\\', '')
          .slice(0, -1);
        // router middleware
        middleware.handle.stack.forEach(function (handler: any) {
          const route = handler.route;
          if (route) {
            route.path = `${parentPath}${route.path}`;
            if (route.path.slice(-1) === '/')
              route.path = route.path.slice(0, -1);
            allRoutes.push(route.path);
          }
        });
      }
    });
    allRoutes.sort();
    const routesNotDocumented = difference(allRoutes, documentedRoutes);
    expect(routesNotDocumented).toEqual([]);
  });
});
