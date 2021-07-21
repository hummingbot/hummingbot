declare function fastq<C, T = any, R = any>(context: C, worker: fastq.worker<C, T, R>, concurrency: number): fastq.queue<T, R>
declare function fastq<C, T = any, R = any>(worker: fastq.worker<C, T, R>, concurrency: number): fastq.queue<T, R>

declare namespace fastq {
  type worker<C, T = any, R = any> = (this: C, task: T, cb: fastq.done<R>) => void
  type done<R = any> = (err: Error | null, result?: R) => void

  interface queue<T = any, R = any> {
    push(task: T, done: done<R>): void
    unshift(task: T, done: done<R>): void
    pause(): any
    resume(): any
    idle(): boolean
    length(): number
    getQueue(): T[]
    kill(): any
    killAndDrain(): any
    concurrency: number
    drain(): any
    empty: () => void
    saturated: () => void
  }
}

export = fastq
