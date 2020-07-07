
import platform


def native_lib_path(libname):
    # get the right filename
    if platform.uname()[0] == "Windows":
        extn = ".dll"
    if platform.uname()[0] == "Darwin":
        extn = ".dylib"
    else:
        extn = ".so"
    return libname + extn


def bytes_to_field_elements(in_bytes, chunk_size=253):
    assert isinstance(in_bytes, bytes)
    as_bits = ''.join([bin(_)[2:].rjust(8, '0') for _ in in_bytes])
    num_bits = len(as_bits)
    chunks = [as_bits[_:_+chunk_size][::-1] for _ in range(0, num_bits, chunk_size)]
    return [int(_, 2) for _ in chunks]


def libsnark2python (inputs):   
    bin_inputs = []
    for x in inputs:
        binary = bin(x)[2:][::-1]
        if len(binary) > 100:
            binary = binary.ljust(253, "0")          
        bin_inputs.append(binary)
    raw = "".join(bin_inputs)

    raw += "0" * (256 * 5 - len(raw)) 

    output = []
    i = 0
    while i < len(raw):
        hexnum = hex(int(raw[i:i+256], 2))
        #pad leading zeros
        padding = 66 - len(hexnum)
        hexnum = hexnum[:2] + "0"*padding + hexnum[2:]

        output.append(hexnum)
        i += 256
    return(output)
