import { Ref, ref } from 'vue'

export interface IBox {
    count: number,
    title: string,
    desc: string,
    href: string,
    linkText: string,
}

export const strategiesBox: Ref<IBox> = ref({
    count: 13,
    title: 'STRATEGIES',
    desc: 'Hummingbot offers various trading strategies, each with its own set of configurable parameters.',
    linkText: 'Documentation',
    href: '/',
}) 