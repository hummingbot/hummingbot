import 'jest-extended';
import { ReferenceCountingCloseable } from '../../src/services/refcounting-closeable';

class RefCountFixture extends ReferenceCountingCloseable {
  private _finalized: boolean;
  private readonly _members: { [key: string]: RefCountFixture };

  constructor(retrievalKey: string) {
    super(retrievalKey);
    this._finalized = false;
    this._members = {};
  }

  get finalized(): boolean {
    return this._finalized;
  }

  get members(): { [key: string]: RefCountFixture } {
    return this._members;
  }

  public async add(memberKey: string) {
    const member: RefCountFixture = RefCountFixture.getInstance(
      memberKey,
      this.handle
    );
    this._members[memberKey] = member;
  }

  public async remove(memberKey: string) {
    if (!(memberKey in this._members)) {
      return;
    }

    const member: RefCountFixture = this._members[memberKey];
    delete this._members[memberKey];
    await member.close(this.handle);
  }

  public async close(ownersHandler: string): Promise<void> {
    await super.close(ownersHandler);
    if (this.refCount < 1) {
      for (const memberKey of Object.keys(this._members)) {
        await this.remove(memberKey);
      }
      this._finalized = true;
    }
  }
}

describe('Reference counting closeable tests', () => {
  const rootHandle: string = ReferenceCountingCloseable.createHandle();

  it('Finalize after being released by owner', async () => {
    const fixture: RefCountFixture = RefCountFixture.getInstance(
      'instance1',
      rootHandle
    );

    try {
      expect(fixture.refCount).toEqual(1);
      expect(fixture.finalized).toBeFalse();
      await fixture.close(rootHandle);
      expect(fixture.refCount).toEqual(0);
      expect(fixture.finalized).toBeTrue();
    } finally {
      await fixture.close(rootHandle);
    }
  });

  it('Do not finalize if more than zero owner left', async () => {
    const owner1: RefCountFixture = RefCountFixture.getInstance(
      'instance1',
      rootHandle
    );
    const owner2: RefCountFixture = RefCountFixture.getInstance(
      'instance2',
      rootHandle
    );
    const sharedObject: RefCountFixture = RefCountFixture.getInstance(
      'shared',
      rootHandle
    );

    try {
      await owner1.add('shared');
      await owner2.add('shared');
      expect(sharedObject.refCount).toEqual(3);
      await sharedObject.close(rootHandle);
      expect(sharedObject.refCount).toEqual(2);
      expect(sharedObject.finalized).toBeFalse();

      await owner1.remove('shared');
      expect(sharedObject.refCount).toEqual(1);
      expect(sharedObject.finalized).toBeFalse();

      await owner2.remove('shared');
      expect(sharedObject.refCount).toEqual(0);
      expect(sharedObject.finalized).toBeTrue();
    } finally {
      await owner1.close(rootHandle);
      await owner2.close(rootHandle);
      await sharedObject.close(rootHandle);
    }
  });

  it('Cascading finalization given an ownership graph', async () => {
    const node1_1: RefCountFixture = RefCountFixture.getInstance(
      'node1_1',
      rootHandle
    );
    const node1_2: RefCountFixture = RefCountFixture.getInstance(
      'node1_2',
      rootHandle
    );
    const node1_3: RefCountFixture = RefCountFixture.getInstance(
      'node1_3',
      rootHandle
    );
    const node2_1: RefCountFixture = RefCountFixture.getInstance(
      'node2_1',
      rootHandle
    );
    const node3_1: RefCountFixture = RefCountFixture.getInstance(
      'node3_1',
      rootHandle
    );
    const node4_1: RefCountFixture = RefCountFixture.getInstance(
      'node4_1',
      rootHandle
    );
    const allNodes: RefCountFixture[] = [
      node1_1,
      node1_2,
      node1_3,
      node2_1,
      node3_1,
      node4_1,
    ];

    try {
      // Connect the nodes together as a dependency tree.
      await node1_1.add('node2_1');
      await node1_2.add('node2_1');
      await node1_3.add('node2_1');
      await node2_1.add('node3_1');
      await node3_1.add('node4_1');

      // Remove the non-top nodes from root ownership.
      await node2_1.close(rootHandle);
      await node3_1.close(rootHandle);
      await node4_1.close(rootHandle);

      // Ensure all nodes are still not finalized.
      expect(node1_1.refCount).toEqual(1);
      expect(node1_2.refCount).toEqual(1);
      expect(node1_3.refCount).toEqual(1);
      expect(node2_1.refCount).toEqual(3);
      expect(node3_1.refCount).toEqual(1);
      expect(node4_1.refCount).toEqual(1);
      for (const n of allNodes) {
        expect(n.finalized).toBeFalse();
      }

      // Close the top nodes.
      await node1_1.close(rootHandle);
      await node1_2.close(rootHandle);
      await node1_3.close(rootHandle);

      // All nodes should be finalized by now.
      for (const n of allNodes) {
        expect(n.finalized).toBeTrue();
      }
    } finally {
      for (const n of allNodes) {
        await n.close(rootHandle);
      }
    }
  });
});
