from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit

def cbarrier(circ, barrier):
    if barrier:
        circ.barrier()


def sum(circ, cin, a, b, barrier=False):
    circ.cx(a, b)
    cbarrier(circ, barrier)
    circ.cx(cin, b)
    cbarrier(circ, barrier)


def sum_dg(circ, cin, a, b, barrier=False):
    circ.cx(cin, b)
    cbarrier(circ, barrier)
    circ.cx(a, b)
    cbarrier(circ, barrier)


def carry(circ, cin, a, b, cout, barrier=False):
    circ.ccx(a, b, cout)
    cbarrier(circ, barrier)
    circ.cx(a, b)
    cbarrier(circ, barrier)
    circ.ccx(cin, b, cout)
    cbarrier(circ, barrier)


def carry_dg(circ, cin, a, b, cout, barrier=False):
    circ.ccx(cin, b, cout)
    cbarrier(circ, barrier)
    circ.cx(a, b)
    cbarrier(circ, barrier)
    circ.ccx(a, b, cout)
    cbarrier(circ, barrier)


creg = 0


def ripple_add(circ: QuantumCircuit, a, b, c, N, barrier=False):
    # Step 1: Compute the most significant bit of the result a+b
    # To achieve this, we achieve all the carries Ci through the relation :
    # C(i+1) <-- Ai AND Bi AND Ci
    for i in range(0, N-1):
        carry(circ, c[i], a[i], b[i], c[i+1], barrier)

    # The last carry contains the first (leftmost) bit of the result a+b
    # As a result, this carry should be considered in the result
    # We store this carry in b[N]
    carry(circ, c[N-1], a[N-1], b[N-1], b[N], barrier)

    # Calculate the second-to-leftmost bit of the sum.
    circ.cx(a[N - 1], b[N - 1])
    cbarrier(circ, barrier)

    sum(circ, c[N-1], a[N-1], b[N-1])

    # Invert the carries and calculate the remaining sums.
    for i in range(N - 2, -1, -1):
        carry_dg(circ, c[i], a[i], b[i], c[i + 1], barrier)
        sum(circ, c[i], a[i], b[i], barrier)

    # Optimization
    # Reset the carry register for reuse
    for i in range(0, N):
        circ.reset(c[i])


def ripple_add_dg(circ: QuantumCircuit, a, b, c, N, barrier=False):
    for i in range(0, N-1):
        sum_dg(circ, c[i], a[i], b[i], barrier)
        carry(circ, c[i], a[i], b[i], c[i + 1], barrier)

    sum_dg(circ, c[N - 1], a[N - 1], b[N - 1])

    circ.cx(a[N - 1], b[N - 1])
    cbarrier(circ, barrier)

    carry_dg(circ, c[N-1], a[N - 1], b[N - 1], b[N], barrier)

    for i in range(N - 2, -1, -1):
        carry_dg(circ, c[i], a[i], b[i], c[i + 1], barrier)

    # Optimization
    # Reset the carry register for reuse
    for i in range(0, N):
        circ.reset(c[i])


def ripple_add_modulo_n(qc, bit_count, a, b, c, mod, of, t, barrier=False):
    ripple_add(qc, a, b, c, bit_count, barrier)
    ripple_add_dg(qc, mod, b, c, bit_count, barrier)

    # The MSB of |b> indicates whether an overflow occurred in the subtraction process
    qc.x(b[bit_count])
    qc.cx(b[bit_count], of[0])
    qc.x(b[bit_count])

    # Set the first operand to state |0>, if overflow is set
    # Copy the value of the first register to the temporary register,
    # Then reset the first register to |0> based on the state of overflow qbit
    for i in range(bit_count):
        qc.cx(mod[i], t[i])
        qc.ccx(of[0], t[i], mod[i])

    ripple_add(qc, mod, b, c, bit_count, barrier)

    # Copy back the value of the temporary register to the first register,
    # Then reset the temporary register to |0> based on the state of overflow qbit
    for i in range(bit_count):
        qc.ccx(of[0], t[i], mod[i])
        qc.cx(mod[i], t[i])

    ripple_add_dg(qc, a, b, c, bit_count, barrier)

    qc.cx(b[bit_count], of[0])

    ripple_add(qc, a, b, c, bit_count, barrier)

    # Optimization
    # Reset the temporary register so it can be reused
    for i in range(0, bit_count):
        qc.reset(t[i])


def ripple_add_modulo_n_dg(qc, bit_count, a, b, c, mod, of, t, barrier=False):
    ripple_add_dg(qc, a, b, c, bit_count, barrier)
    ripple_add(qc, mod, b, c, bit_count, barrier)

    qc.x(b[bit_count])
    qc.cx(b[bit_count], of[0])
    qc.x(b[bit_count])

    # Set the first operand to state |0>, if overflow is set
    for i in range(bit_count):
        qc.ccx(of[0], t[i], mod[i])
        qc.cx(mod[i], t[i])

    ripple_add_dg(qc, mod, b, c, bit_count, barrier)

    # Set the first operand to state |0>, if overflow is set
    for i in range(bit_count):
        qc.cx(mod[i], t[i])
        qc.ccx(of[0], t[i], mod[i])

    ripple_add(qc, a, b, c, bit_count, barrier)

    qc.cx(b[bit_count], of[0])

    ripple_add_dg(qc, a, b, c, bit_count, barrier)

    # Optimization
    # Reset the temporary register so it can be reused
    for i in range(0, bit_count):
        qc.reset(t[i])


def set_reg_bits(qc, num, reg):
    n = num.bit_length()
    for i in range(n):
        if num & (1 << i):
            qc.x(reg[i])


def create_circuit(a_dec, b_dec, bit_count):

    # Registers for the input numbers
    a = QuantumRegister(bit_count, 'a')
    b = QuantumRegister(bit_count + 1, 'b')

    # Register to store the carry results
    c = QuantumRegister(bit_count, 'c')

    # Registers for the output classical bits
    ca = ClassicalRegister(bit_count, 'ca')
    cb = ClassicalRegister(bit_count + 1, 'cb')

    qc = QuantumCircuit(a, b, c, ca, cb)

    # Index of the qubit is the most significant bit of the binary number
    # For example, in the binary number '1000', having bit-length N=4, the most significant bit is '1'
    # In order to set the qubit representing this bit to state |0>, we need to apply the X gate
    # to qubit at index N-1 = 3
    # So, the following would set the leftmost bit to state |0> : qc.x(a[3])
    # This also holds true in the state representation of bits in the measured results

    for i in range(0, bit_count):
        if a_dec & (1 << i) != 0:
            qc.x(a[i])
        if b_dec & (1 << i) != 0:
            qc.x(b[i])

    return qc, a, b, c, ca, cb
