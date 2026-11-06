import streamlit as st
import pandas as pd
from collections import defaultdict
from itertools import product
from io import StringIO

st.set_page_config(
    page_title="LogicMin | Boolean Minimizer",
    page_icon="⚡",
    layout="wide",
)

# -------------------- Quine-McCluskey algorithm --------------------

def to_bin(n, bits):
    return format(n, f"0{bits}b")


def combine(a, b):
    """Combine implicants that differ in exactly one fixed bit."""
    result = []
    differences = 0

    for x, y in zip(a, b):
        if x == y:
            result.append(x)
        elif x != "-" and y != "-":
            differences += 1
            result.append("-")
            if differences > 1:
                return None
        else:
            # A dash must occur in the same position in both implicants.
            return None

    return "".join(result) if differences == 1 else None


def find_prime_implicants(terms, bits):
    current = {to_bin(m, bits): {m} for m in sorted(set(terms))}
    primes = {}
    stages = []
    column = 0

    while current:
        groups = defaultdict(list)
        for implicant in current:
            groups[implicant.count("1")].append(implicant)

        stage = {
            "column": column,
            "groups": [
                {
                    "ones": ones,
                    "items": [
                        {"implicant": imp, "covered": sorted(current[imp])}
                        for imp in sorted(groups[ones])
                    ],
                }
                for ones in sorted(groups)
            ],
        }

        used = set()
        next_terms = {}

        for ones in sorted(groups):
            if ones + 1 not in groups:
                continue
            for a in groups[ones]:
                for b in groups[ones + 1]:
                    combined = combine(a, b)
                    if combined is not None:
                        used.update((a, b))
                        next_terms.setdefault(combined, set())
                        next_terms[combined].update(current[a] | current[b])

        for imp, covered in current.items():
            if imp not in used:
                primes.setdefault(imp, set()).update(covered)

        stage["combined"] = [
            {"implicant": imp, "covered": sorted(cov)}
            for imp, cov in sorted(next_terms.items())
        ]
        stages.append(stage)
        current = next_terms
        column += 1

    return primes, stages


def petrick(remaining, primes):
    """Return a minimum PI set: fewest terms, then fewest literals."""
    products = {frozenset()}

    for minterm in remaining:
        choices = frozenset(
            pi for pi, covered in primes.items() if minterm in covered
        )
        if not choices:
            raise ValueError(f"No prime implicant covers minterm {minterm}.")

        expanded = {
            existing | {pi}
            for existing in products
            for pi in choices
        }

        # Absorption: discard any product that is a strict superset.
        products = {
            candidate for candidate in expanded
            if not any(other < candidate for other in expanded)
        }

    def literal_count(selection):
        return sum(sum(ch != "-" for ch in pi) for pi in selection)

    best_cost = min((len(p), literal_count(p)) for p in products)
    return [
        set(p) for p in products
        if (len(p), literal_count(p)) == best_cost
    ]


def implicant_to_term(implicant, variable_names):
    pieces = []
    for bit, name in zip(implicant, variable_names):
        if bit == "1":
            pieces.append(name)
        elif bit == "0":
            pieces.append(name + "'")
    return "".join(pieces) if pieces else "1"


def minimize(minterms, dont_cares, bits):
    minterms = sorted(set(minterms))
    dont_cares = sorted(set(dont_cares) - set(minterms))

    if not minterms:
        return {
            "expression": "0",
            "selected": [],
            "primes": {},
            "stages": [],
            "chart": {},
            "essential": set(),
            "remaining": [],
            "all_optimal": [[]],
        }

    max_term = 2 ** bits - 1
    invalid = [m for m in minterms + dont_cares if m < 0 or m > max_term]
    if invalid:
        raise ValueError(
            f"Values {invalid} are outside the valid range 0 to {max_term} "
            f"for {bits} variables."
        )

    primes, stages = find_prime_implicants(minterms + dont_cares, bits)

    chart = {
        m: sorted(pi for pi, covered in primes.items() if m in covered)
        for m in minterms
    }

    if any(not choices for choices in chart.values()):
        raise ValueError("At least one minterm is not covered by any prime implicant.")

    essential = {
        choices[0] for choices in chart.values() if len(choices) == 1
    }

    covered_by_essential = set()
    for pi in essential:
        covered_by_essential.update(primes[pi])

    remaining = [m for m in minterms if m not in covered_by_essential]

    if remaining:
        alternatives = petrick(remaining, primes)
        all_optimal = [
            sorted(essential | alternative)
            for alternative in alternatives
        ]
    else:
        all_optimal = [sorted(essential)]

    all_optimal = sorted(
        {tuple(item) for item in all_optimal},
        key=lambda x: (len(x), sum(sum(c != "-" for c in pi) for pi in x), x),
    )
    selected = list(all_optimal[0])

    variable_names = [chr(ord("A") + i) for i in range(bits)]
    expression = " + ".join(
        implicant_to_term(pi, variable_names) for pi in selected
    )

    return {
        "expression": expression,
        "selected": selected,
        "primes": primes,
        "stages": stages,
        "chart": chart,
        "essential": essential,
        "remaining": remaining,
        "all_optimal": [list(x) for x in all_optimal],
    }


# -------------------- Input helpers and truth table --------------------

def parse_terms(raw):
    if not raw.strip():
        return []
    try:
        values = [int(token) for token in raw.replace(",", " ").split()]
    except ValueError:
        raise ValueError("Enter only whole numbers separated by spaces or commas.")
    if any(value < 0 for value in values):
        raise ValueError("Minterms and don't-care terms cannot be negative.")
    return sorted(set(values))


def make_truth_table(bits, minterms, dont_cares, selected):
    names = [chr(ord("A") + i) for i in range(bits)]
    rows = []
    for values in product([0, 1], repeat=bits):
        index = int("".join(map(str, values)), 2)
        if index in dont_cares:
            output = "X"
        elif index in minterms:
            output = 1
        else:
            output = 0

        covered = any(
            all(bit == "-" or int(bit) == value
                for bit, value in zip(imp, values))
            for imp in selected
        )
        rows.append({**dict(zip(names, values)), "Minterm": index,
                     "F (given)": output,
                     "F (minimized)": int(covered)})
    return pd.DataFrame(rows)


# -------------------- Dashboard UI --------------------

st.title("⚡ LogicMin")
st.caption("Boolean expression minimizer using the Quine–McCluskey tabular method")

with st.sidebar:
    st.header("Function input")
    variable_count = st.selectbox("Number of variables", list(range(2, 9)), index=2)
    st.caption(
        f"Variables: {', '.join(chr(65+i) for i in range(variable_count))} "
        f"(A is the most significant bit)"
    )
    minterm_text = st.text_input(
        "Minterms",
        value="0, 1, 2, 5, 6, 7, 8, 9, 10, 14",
        help="Example: 0, 1, 2, 5, 6",
    )
    dont_care_text = st.text_input(
        "Don't-care terms (optional)",
        value="",
        help="Example: 3, 11, 15",
    )
    run = st.button("Minimize expression", type="primary", use_container_width=True)

st.info(
    "Enter the minterms and select the original number of variables. "
    "Don't-care terms are optional and do not need to be covered."
)

if "result" not in st.session_state:
    st.session_state.result = None
    st.session_state.input_signature = None

if run:
    try:
        minterms = parse_terms(minterm_text)
        dont_cares = parse_terms(dont_care_text)
        if not minterms:
            raise ValueError("Enter at least one minterm.")
        overlap = sorted(set(minterms) & set(dont_cares))
        if overlap:
            dont_cares = [x for x in dont_cares if x not in overlap]

        result = minimize(minterms, dont_cares, variable_count)
        st.session_state.result = result
        st.session_state.input_signature = (
            variable_count, tuple(minterms), tuple(dont_cares)
        )
        st.session_state.current_minterms = minterms
        st.session_state.current_dont_cares = dont_cares
    except ValueError as error:
        st.error(str(error))
        st.session_state.result = None

result = st.session_state.result
if result is not None:
    bits, minterms, dont_cares = st.session_state.input_signature
    st.divider()
    st.subheader("Minimization result")

    col1, col2, col3 = st.columns(3)
    col1.metric("Variables", bits)
    col2.metric("Prime implicants", len(result["primes"]))
    col3.metric("Selected implicants", len(result["selected"]))

    st.success(f"Minimized SOP expression:  **F = {result['expression']}**")

    if len(result["all_optimal"]) > 1:
        with st.expander("Other equally optimal solutions"):
            for index, solution in enumerate(result["all_optimal"], start=1):
                names = [chr(ord("A") + i) for i in range(bits)]
                expression = " + ".join(
                    implicant_to_term(pi, names) for pi in solution
                )
                st.write(f"{index}. F = {expression}")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Combining stages", "Prime implicant chart",
        "Truth table", "Final details"
    ])

    with tab1:
        st.subheader("Tabular combining process")
        for stage in result["stages"]:
            with st.expander(f"Column {stage['column']}", expanded=(stage["column"] == 0)):
                for group in stage["groups"]:
                    st.markdown(f"**Group {group['ones']} (number of 1s)**")
                    frame = pd.DataFrame(group["items"])
                    frame.columns = ["Implicant", "Minterms covered"]
                    st.dataframe(frame, hide_index=True, use_container_width=True)
                if stage["combined"]:
                    st.markdown("**Combined implicants for next column**")
                    frame = pd.DataFrame(stage["combined"])
                    frame.columns = ["New implicant", "Minterms covered"]
                    st.dataframe(frame, hide_index=True, use_container_width=True)
                else:
                    st.caption("No further combinations in this column.")

    with tab2:
        st.subheader("Prime implicant chart")
        chart_rows = []
        for pi in sorted(result["primes"]):
            row = {"Prime implicant": pi}
            for m in minterms:
                row[str(m)] = "X" if m in result["primes"][pi] else ""
            row["Essential"] = "Yes" if pi in result["essential"] else ""
            row["Selected"] = "Yes" if pi in result["selected"] else ""
            chart_rows.append(row)
        st.dataframe(pd.DataFrame(chart_rows), hide_index=True, use_container_width=True)
        st.write("Essential prime implicants:", ", ".join(sorted(result["essential"])) or "None")
        st.write("Minterms remaining after essentials:", result["remaining"] or "None")
        if result["remaining"]:
            st.caption("Petrick's method is used to cover the remaining minterms.")

    with tab3:
        st.subheader("Truth table")
        truth = make_truth_table(bits, minterms, dont_cares, result["selected"])
        st.dataframe(truth, hide_index=True, use_container_width=True)
        st.download_button(
            "Download truth table (CSV)",
            data=truth.to_csv(index=False).encode("utf-8"),
            file_name="logicmin_truth_table.csv",
            mime="text/csv",
        )

    with tab4:
        st.subheader("Selected implicants")
        names = [chr(ord("A") + i) for i in range(bits)]
        details = []
        for pi in result["selected"]:
            details.append({
                "Implicant": pi,
                "Product term": implicant_to_term(pi, names),
                "Minterms covered": sorted(result["primes"][pi]),
                "Literals": pi.count("0") + pi.count("1"),
                "Essential": "Yes" if pi in result["essential"] else "No",
            })
        st.dataframe(pd.DataFrame(details), hide_index=True, use_container_width=True)

        report = StringIO()
        report.write("LogicMin - Quine-McCluskey result\n")
        report.write(f"Variables: {bits}\n")
        report.write(f"Minterms: {minterms}\n")
        report.write(f"Don't-cares: {dont_cares}\n")
        report.write(f"Selected implicants: {result['selected']}\n")
        report.write(f"Minimized expression: F = {result['expression']}\n")
        st.download_button(
            "Download result (TXT)",
            data=report.getvalue(),
            file_name="logicmin_result.txt",
            mime="text/plain",
        )
else:
    st.markdown("### How to use")
    st.markdown(
        "1. Select the number of variables.\n"
        "2. Enter minterms separated by commas or spaces.\n"
        "3. Optionally enter don't-care terms.\n"
        "4. Click **Minimize expression** to see the solution and working."
    )
    st.markdown("### Method")
    st.write(
        "LogicMin uses binary grouping, iterative implicant combination, "
        "prime implicant chart reduction, and Petrick's method when needed."
    )

st.divider()
st.caption("LogicMin • Educational tool • Quine–McCluskey tabular minimization")
