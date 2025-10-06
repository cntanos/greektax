# 2026 Ministry employment tax credit reference

*Observed: 6 October 2025 via https://www.taxcalc2025.minfin.gr/ main-ASFKXBUP.js*

The production calculator bundles the wage income logic in the `fo` class. Relevant excerpt:

```
var Yb={amount:[777,900,1120,1340,1580,1780,2000,2200,2440,2660,2880,3100,3320,3540,3760,3980]};
...
calculateTaxWithBracketResults(r,e,o){
  let i=new Io; this.annualTaxableIncome=r; this.kids=e ?? 0;
  let credit=0, reduction=0;
  if(r>0 && o===1){
    credit = Yb.amount[this.kids];
    if(r>12000 && e<5){
      reduction = (r-12000)/1000*20;
      credit = Math.max(0, credit - reduction);
    }
  }
  i.taxDeductions = credit;
  ...
}
```

Key takeaways:

- The credit ladder matches `[777, 900, 1120, 1340, 1580, 1780, 2000, 2200, 2440, 2660, 2880, 3100, 3320, 3540, 3760, 3980]` for dependants 0–15.
- The reduction applies only when the taxpayer is in profession code `1` (dependent employment) and has fewer than five dependants.
- For dependants 0–4, the credit phases out at **20 € per 1 000 €** of declared wage income above 12 000 €, clipping at zero when the reduction exceeds the base credit.
- From five dependants onwards the calculator leaves the credit unchanged regardless of income: there is no phase-out for the higher ladders.

Regression figures captured for audit (employment only, 2026 tables, no contributions):

| Dependants | 12 000 € | 20 000 € | 30 000 € | 50 000 € | 70 000 € |
|-----------:|---------:|---------:|---------:|---------:|---------:|
| 0 | credit 777 €, tax before credit 1 300 € | 617 €, 2 900 € | 417 €, 5 500 € | 17 €, 12 800 € | 0 €, 21 100 € |
| 1 | 900 €, 1 260 € | 740 €, 2 700 € | 540 €, 5 100 € | 140 €, 12 400 € | 0 €, 20 700 € |
| 2 | 1 120 €, 1 220 € | 960 €, 2 500 € | 760 €, 4 700 € | 360 €, 12 000 € | 0 €, 20 300 € |
| 3 | 1 080 €, 1 080 € | 1 180 €, 1 800 € | 980 €, 3 800 € | 580 €, 11 100 € | 180 €, 19 400 € |
| 4 | 0 €, 0 € | 0 €, 0 € | 1 220 €, 1 800 € | 820 €, 9 100 € | 420 €, 17 400 € |
| 5 | 0 €, 0 € | 0 €, 0 € | 1 600 €, 1 600 € | 1 780 €, 8 900 € | 1 780 €, 17 200 € |
| 6 | 0 €, 0 € | 0 €, 0 € | 1 400 €, 1 400 € | 2 000 €, 8 700 € | 2 000 €, 17 000 € |
| 7 | 0 €, 0 € | 0 €, 0 € | 1 400 €, 1 400 € | 2 200 €, 8 700 € | 2 200 €, 17 000 € |
| 8 | 0 €, 0 € | 0 €, 0 € | 1 400 €, 1 400 € | 2 440 €, 8 700 € | 2 440 €, 17 000 € |
| 9 | 0 €, 0 € | 0 €, 0 € | 1 400 €, 1 400 € | 2 660 €, 8 700 € | 2 660 €, 17 000 € |
| 10 | 0 €, 0 € | 0 €, 0 € | 1 400 €, 1 400 € | 2 880 €, 8 700 € | 2 880 €, 17 000 € |

These align with the bundled ministry calculator and inform the automated regression tests.
