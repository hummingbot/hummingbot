import { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {path: '', redirect: 'strategies'},
  {
    path: '/strategies',
    component: () => import('../pages/Strategies/Layout.vue'),
  },

  // Always leave this as last one,
  // but you can also remove it
  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/Error404.vue'),
  },
];

export default routes;
