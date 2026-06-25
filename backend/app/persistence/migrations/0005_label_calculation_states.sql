CREATE TABLE IF NOT EXISTS label_calculation_states (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    label_code TEXT NOT NULL,
    label_name TEXT NOT NULL,
    category TEXT NOT NULL,
    state TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    observed TEXT NOT NULL,
    threshold TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    PRIMARY KEY (run_id, fund_code, label_code)
);
