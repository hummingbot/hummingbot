
def fq_to_sol(o):
    return '%s' % (hex(o.n),)


def fq2_to_sol(o):
    # Fq2 is big-endian in EVM, so '[c1, c0]'
    return '[%s, %s]' % (fq_to_sol(o.coeffs[1]), fq_to_sol(o.coeffs[0]))


def g2_to_sol(o):
    return 'Pairing.G2Point(%s, %s)' % (fq2_to_sol(o[0]), fq2_to_sol(o[1]))


def g1_to_sol(o):
    return 'Pairing.G1Point(%s, %s)' % (fq_to_sol(o[0]), fq_to_sol(o[1]))
