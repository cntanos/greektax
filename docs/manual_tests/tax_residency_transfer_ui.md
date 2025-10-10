# Tax Residency Transfer UI Verification

Manual UI verification was executed with Playwright against the local Flask
server using `index-local.html` to point the static bundle at the API. The test
scenario followed the steps below:

1. Select tax year 2024.
2. Enable the employment income section and enter €40,000 as annual gross salary.
3. Run the calculation to capture the baseline taxable income and tax total.
4. Enable the “Tax residency transfer to Greece” checkbox and recalculate.

Observed outputs:

- Baseline taxable income: €34,452.00
- Baseline tax total: €7,285.72
- With residency transfer taxable income: €17,226.00
- With residency transfer tax total: €2,272.72

The taxable income halves exactly while the tax total drops significantly,
confirming that the statutory 50% exemption is applied in the UI workflow.
