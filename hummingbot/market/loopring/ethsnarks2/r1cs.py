from .field import FQ

def r1cs_constraint(a, b, c):
	if not isinstance(a, FQ):
		a = FQ(a)
	if not isinstance(b, FQ):
		b = FQ(b)
	if not isinstance(c, FQ):
		c = FQ(c)
	if not a * b == c:
		raise RuntimeError("R1CS Constraint Failed!")
