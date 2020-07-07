# Copyright (c) 2018-2019 HarryR
# License: LGPL-3.0+

import hashlib
import math
from collections import namedtuple

from .poseidon import poseidon, DefaultParams as poseidon_DefaultParams
from .mimc import mimc_hash
from .field import FQ, SNARK_SCALAR_FIELD


class MerkleProof(namedtuple('_MerkleProof', ('leaf', 'address', 'path', 'hasher', 'width'))):
    def verify(self, root):
        item = self.leaf
        for depth, (index, proof) in enumerate(zip(self.address, self.path)):
            hasher_args = proof[::] if isinstance(proof, list) else [proof]
            hasher_args.insert(index, item)
            item = self.hasher.hash_node(depth, *hasher_args)
        return root == item


class Abstract_MerkleHasher(object):
    def unique(self, depth, index):
        """
        Derive a unique hash for a leaf which doesn't exist in the tree
        This allows for an incremental tree to be constructed, where the
        remaining nodes which don't exist yet are 'filled-in' with these placeholders
        """
        assert depth < self._tree_depth
        item = int(depth).to_bytes(2, 'big') + int(index).to_bytes(30, 'big')
        hasher = hashlib.sha256()
        hasher.update(item)
        return int.from_bytes(hasher.digest(), 'big') % SNARK_SCALAR_FIELD

    def _make_IVs(self):
        out = []
        hasher = hashlib.sha256()
        for i in range(self._tree_depth):
            item = int(i).to_bytes(2, 'little')
            hasher.update(b'MerkleTree-' + item)
            digest = int.from_bytes(hasher.digest(), 'big') % SNARK_SCALAR_FIELD
            out.append(digest)
        return out

    def valid(self, item):
        return isinstance(item, int) and item > 0 and item < SNARK_SCALAR_FIELD


# TODO: move to ethsnarks.mimc ?
class MerkleHasher_MiMC(Abstract_MerkleHasher):
    def __init__(self, tree_depth, node_width=2):
        if node_width != 2:
            raise ValueError("Invalid node width %r, must be 2" % (node_width,))
        self._tree_depth = tree_depth
        self._IVs = self._make_IVs()

    def hash_node(self, depth, *args):
        return mimc_hash(args, self._IVs[depth])


# TODO: move to ethsnarks.poseidon?
class MerkleHasher_Poseidon(Abstract_MerkleHasher):
    def __init__(self, params, depth, node_width=2):
        assert node_width > 0
        if params is None:
            params = poseidon_DefaultParams
        if node_width >= (params.t - 1) or node_width <= 0:
            raise ValueError("Node width must be in range: 0 < width < (t-1)")
        self._params = params
        self._tree_depth = depth

    @classmethod
    def factory(cls, params=None):
        return lambda *args, **kwa: cls(params, *args, **kwa)

    def hash_node(self, depth, *args):
        return poseidon(args, params=self._params)


DEFAULT_HASHER = MerkleHasher_MiMC


class MerkleTree(object):
    """
    With a tree of depth 2 and width 4, contains 16 items:

        offsets:  0 1 2 3   4 5 6 7   8 9 . .   . . . .
        level 0: [A B C D] [E F G H] [I J K L] [M N O P]
        level 1: [Q R S T]
        level 2: [U]

    Our item is `G`, which is at position `[1][2]`
    The tree is equivalent to:

        level1: [Q=H(A,B,C,D) R=H(E,F G H) S=H(I,J,K,L) T=H(M,N,O,P)]
        level2: [U=H(Q,R,S,T)]

    The proof for our item `G` will be:

        [(2, [E F H]), (1, [Q S T])]

    Each element of the proof supplies the index that the previous output will be inserted
    into the list of other elements in the hash to re-construct the root
    """
    def __init__(self, n_items, width=2, hasher=None):
        assert n_items >= width
        assert (n_items % width) == 0
        if hasher is None:
            hasher = DEFAULT_HASHER
        self._width = width
        self._tree_depth = int(math.log(n_items, width))
        self._hasher = hasher(self._tree_depth, width)
        self._n_items = n_items
        self._cur = 0
        self._leaves = [list() for _ in range(0, self._tree_depth + 1)]

    def __len__(self):
        return self._cur

    def update(self, index, leaf):
        if isinstance(leaf, FQ):
            leaf = leaf.n
        if not isinstance(leaf, int):
            raise TypeError("Invalid leaf")
        assert leaf >= 0 and leaf < SNARK_SCALAR_FIELD
        if (len(self._leaves[0]) - 1) < index:
            raise KeyError("Out of bounds")
        self._leaves[0][index] = leaf
        self._updateTree(index)

    def append(self, leaf):
        if self._cur >= (self._n_items):
            raise RuntimeError("Tree Full")
        if isinstance(leaf, FQ):
            leaf = leaf.n
        assert leaf >= 0 and leaf < SNARK_SCALAR_FIELD
        self._leaves[0].append(leaf)
        self._updateTree()
        self._cur += 1
        return self._cur - 1

    def __getitem__(self, key):
        if not isinstance(key, int):
            raise TypeError("Invalid key")
        if key < 0 or key >= self._cur:
            raise KeyError("Out of bounds")
        return self._leaves[0][key]

    def __setitem__(self, key, value):
        self.update(key, value)

    def __contains__(self, key):
        return key in self._leaves[0]

    def index(self, leaf):
        return self._leaves[0].index(leaf)

    def _make_node(self, depth, index):
        node_start = index - (index % self._width)
        return [self.leaf(depth, _) for _ in range(node_start, node_start + self._width)]

    def proof(self, index):
        leaf = self[index]
        if index >= self._cur:
            raise RuntimeError("Proof for invalid item!")
        address_bits = list()
        merkle_proof = list()
        for depth in range(self._tree_depth):
            proof_items = self._make_node(depth, index)
            proof_items.remove(proof_items[index % self._width])
            if len(proof_items) == 1:
                proof_items = proof_items[0]
            address_bits.append( index % self._width )
            merkle_proof.append( proof_items )
            index = index // self._width
        return MerkleProof(leaf, address_bits, merkle_proof, self._hasher, self._width)

    def _updateTree(self, cur_index=None):
        cur_index = self._cur if cur_index is None else cur_index
        for depth in range(self._tree_depth):
            next_index = cur_index // self._width
            node_items = self._make_node(depth, cur_index)
            node = self._hasher.hash_node(depth, *node_items)
            if len(self._leaves[depth+1]) == next_index:
                self._leaves[depth+1].append(node)
            else:
                self._leaves[depth+1][next_index] = node
            cur_index = next_index

    def leaf(self, depth, offset):
        if offset >= len(self._leaves[depth]):
            return self._hasher.unique(depth, offset)
        return self._leaves[depth][offset]

    @property
    def root(self):
        if self._cur == 0:
            return None
        return self._leaves[self._tree_depth][0]
