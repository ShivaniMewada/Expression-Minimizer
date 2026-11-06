# LogicMin — Streamlit Boolean Minimizer

## Run locally

1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. (Optional but recommended) Create and activate a virtual environment.
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Start the dashboard:

   ```bash
   streamlit run app.py
   ```

6. Streamlit will open the dashboard in your browser (usually at http://localhost:8501).

## Features

- Quine–McCluskey tabular minimization
- Optional don't-care terms
- Combining columns
- Prime implicant chart
- Essential prime implicants
- Petrick's method for remaining minterms
- Truth table
- CSV and TXT downloads

Variable order is A as MSB, then B, C, etc.
