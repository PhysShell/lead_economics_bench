# Research-question answers

Generated from run data. The verdict column applies the **preregistered** rule (docs/benchmark-spec.md): the paired 95% bootstrap interval on **net_value_per_1k_leads** must exclude zero AND the difference must exceed **2.0%** of the reference's level. `oracle%` columns are the same comparison on the readable 0-100 scale (0 = do nothing, 100 = Oracle).

## RQ1  decision model vs end-to-end analytics

```
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k   ci_low  ci_high  rel_pct                   verdict
    agent_time_heterogeneity      57.77      39.45         18.32     19784.70 12073.03 28185.81     9.62                    BETTER
capacity_value_heterogeneity      50.22      31.54         18.68     38931.37 18917.90 65982.54     8.84                    BETTER
               concept_drift      71.32      17.01         54.31      1628.18   291.79  3230.08     2.20                    BETTER
            delayed_censored      61.77      40.70         21.06     22973.45 16707.81 30190.54    11.07                    BETTER
             easy_randomized      62.05      39.26         22.80     24863.27 18873.90 31269.37    12.07                    BETTER
          hidden_confounding      51.84      35.31         16.53     18900.05 10267.69 29328.48     7.54                    BETTER
      misleading_attribution      61.87      42.79         19.09     20169.82 16509.07 23204.00     9.53                    BETTER
negative_control_null_effect        NaN        NaN           NaN       -14.31   -25.08    -3.47    -0.01 worse but below threshold
                   noisy_crm      56.41      40.10         16.30     17786.09 12608.76 23024.64     8.62                    BETTER
        observed_confounding      62.70      35.31         27.39     31322.07 21902.10 42494.24    12.49                    BETTER
        policy_feedback_loop      60.36      37.70         22.66     24712.63 19113.14 30277.01    12.10                    BETTER
       propensity_not_uplift      35.71      37.15         -1.44     -1045.43 -5000.57  2533.16    -0.34               no evidence
                rare_outcome      65.11      34.75         30.35     15426.84 10918.46 21388.09    18.19                    BETTER
           seasonality_trend      56.66      38.13         18.53     22941.23 16189.55 30299.46     8.97                    BETTER
              selection_bias      62.63      39.45         23.19     25287.60 21023.48 29615.97    12.27                    BETTER
                      sparse      59.73      42.52         17.21     20564.04 15469.58 27434.86     9.80                    BETTER
        strong_heterogeneity      63.09      31.13         31.96     55787.68 49728.79 61632.82    25.66                    BETTER
         value_heterogeneity      52.67      36.52         16.15     32866.11 23132.10 43019.78    10.08                    BETTER
           very_rare_outcome      62.48      37.21         25.27      6269.02  3029.55 10101.39    14.26                    BETTER

-- strongest causal candidate vs the same baseline --
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k   ci_low  ci_high  rel_pct                   verdict
    agent_time_heterogeneity      53.72      39.45         14.27     15410.80  8819.31 24045.56     7.49                    BETTER
capacity_value_heterogeneity      60.84      31.54         29.30     61064.00 35410.00 89012.59    13.87                    BETTER
               concept_drift      35.01      17.01         18.00       539.59  -325.78  1468.79     0.73               no evidence
            delayed_censored      58.07      40.70         17.36     18935.39 10354.18 30305.11     9.13                    BETTER
             easy_randomized      58.49      39.26         19.23     20977.95 13124.19 30066.02    10.19                    BETTER
          hidden_confounding      52.12      35.31         16.81     19215.70 10580.36 29011.12     7.67                    BETTER
      misleading_attribution      57.27      42.79         14.48     15300.50 11899.01 19589.07     7.23                    BETTER
negative_control_null_effect        NaN        NaN           NaN       -15.51   -23.85    -7.30    -0.01 worse but below threshold
        observed_confounding      60.34      35.31         25.03     28616.61 18764.91 39709.61    11.42                    BETTER
        policy_feedback_loop      54.05      37.70         16.35     17837.76  9588.33 26073.35     8.73                    BETTER
       propensity_not_uplift      49.42      37.15         12.27      8938.61  5040.93 12986.86     2.89                    BETTER
                rare_outcome      54.42      34.75         19.67      9997.42  5317.53 15169.06    11.79                    BETTER
           seasonality_trend      57.49      38.13         19.37     23971.93 15498.39 33934.38     9.37                    BETTER
              selection_bias      61.70      39.45         22.26     24274.85 18886.56 30599.40    11.78                    BETTER
                      sparse      54.83      42.52         12.31     14712.05  8299.55 21687.13     7.01                    BETTER
        strong_heterogeneity      68.30      31.13         37.17     64881.85 55590.11 74963.63    29.84                    BETTER
         value_heterogeneity      50.79      36.52         14.27     29039.06 10483.14 51500.49     8.91                    BETTER
           very_rare_outcome      46.45      37.21          9.24      2292.02   -75.22  5204.06     5.21               no evidence
```

## RQ2  uplift vs ordinary lead scoring

```
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k    ci_low  ci_high  rel_pct                   verdict
    agent_time_heterogeneity      53.72      36.30         17.42     18820.75   8889.76 30984.25     9.30                    BETTER
capacity_value_heterogeneity      60.84      26.33         34.51     71933.70  47625.78 96708.60    16.75                    BETTER
               concept_drift      35.01      61.51        -26.50      -794.48  -1561.41   -91.29    -1.05 worse but below threshold
            delayed_censored      58.07      56.10          1.97      2143.51  -4084.78 11499.98     0.96               no evidence
             easy_randomized      58.49      56.21          2.28      2489.80  -3951.32 10871.26     1.11               no evidence
          hidden_confounding      52.12      47.43          4.69      5362.78    138.67 11704.77     2.03                    BETTER
      misleading_attribution      57.27      57.20          0.07        71.23  -4866.05  4939.25     0.03               no evidence
negative_control_null_effect        NaN        NaN           NaN        -8.35    -17.40    -1.13    -0.01 worse but below threshold
        observed_confounding      60.34      58.18          2.15      2464.10  -4550.98  8884.83     0.89               no evidence
        policy_feedback_loop      54.05      54.52         -0.47      -508.17  -5958.41  5560.00    -0.23               no evidence
       propensity_not_uplift      49.42      26.93         22.49     16383.36  11355.16 22356.97     5.42                    BETTER
                rare_outcome      54.42      64.86        -10.44     -5303.65  -7744.28 -3233.72    -5.30                     WORSE
           seasonality_trend      57.49      50.60          6.90      8537.14   -619.13 19350.00     3.15               no evidence
              selection_bias      61.70      57.01          4.69      5113.03   -598.51 11445.99     2.27               no evidence
                      sparse      54.83      54.33          0.50       599.25  -3159.39  4955.78     0.27               no evidence
        strong_heterogeneity      68.30      54.26         14.03     24496.06   8647.40 46053.95     9.50                    BETTER
         value_heterogeneity      50.79      49.04          1.75      3563.43 -13398.02 24470.32     1.01               no evidence
           very_rare_outcome      46.45      64.09        -17.65     -4377.56  -6332.75 -2644.30    -8.65                     WORSE

-- and the economic-but-not-causal rung --
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k   ci_low  ci_high  rel_pct                    verdict
    agent_time_heterogeneity      57.77      36.30         21.47     23194.65 14548.69 33918.72    11.47                     BETTER
capacity_value_heterogeneity      50.22      26.33         23.90     49801.07 34592.93 65268.39    11.60                     BETTER
               concept_drift      71.32      61.51          9.81       294.11  -211.26   910.87     0.39                no evidence
            delayed_censored      61.77      56.10          5.67      6181.58  1178.52 11486.59     2.76                     BETTER
             easy_randomized      62.05      56.21          5.85      6375.12  1737.09 11706.05     2.84                     BETTER
          hidden_confounding      51.84      47.43          4.41      5047.14  1232.30  9333.55     1.91 better but below threshold
      misleading_attribution      61.87      57.20          4.68      4940.54   788.14  8572.16     2.18                     BETTER
negative_control_null_effect        NaN        NaN           NaN        -7.15   -17.89     2.79    -0.00                no evidence
                   noisy_crm      56.41      50.99          5.41      5905.00  -374.62 12408.78     2.71                no evidence
        observed_confounding      62.70      58.18          4.52      5169.56  1642.40  7994.48     1.87 better but below threshold
        policy_feedback_loop      60.36      54.52          5.84      6366.70  2312.48 10591.04     2.86                     BETTER
       propensity_not_uplift      35.71      26.93          8.79      6399.32  2273.22 10324.09     2.12                     BETTER
                rare_outcome      65.11      64.86          0.25       125.78 -2047.94  2293.76     0.13                no evidence
           seasonality_trend      56.66      50.60          6.06      7506.43  2725.12 13313.24     2.77                     BETTER
              selection_bias      62.63      57.01          5.62      6125.77   783.19 12215.23     2.72                     BETTER
                      sparse      59.73      54.33          5.40      6451.24  4745.34  8094.56     2.88                     BETTER
        strong_heterogeneity      63.09      54.26          8.82     15401.90  7156.35 26485.06     5.97                     BETTER
         value_heterogeneity      52.67      49.04          3.63      7390.49 -3636.64 19174.78     2.10                no evidence
           very_rare_outcome      62.48      64.09         -1.61      -400.56 -1121.53   412.75    -0.79                no evidence
```

## RQ3  explicit economics vs a probability score

```
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k   ci_low  ci_high  rel_pct                    verdict
    agent_time_heterogeneity      57.77      36.30         21.47     23194.65 14548.69 33918.72    11.47                     BETTER
capacity_value_heterogeneity      50.22      26.33         23.90     49801.07 34592.93 65268.39    11.60                     BETTER
               concept_drift      71.32      61.51          9.81       294.11  -211.26   910.87     0.39                no evidence
            delayed_censored      61.77      56.10          5.67      6181.58  1178.52 11486.59     2.76                     BETTER
             easy_randomized      62.05      56.21          5.85      6375.12  1737.09 11706.05     2.84                     BETTER
          hidden_confounding      51.84      47.43          4.41      5047.14  1232.30  9333.55     1.91 better but below threshold
      misleading_attribution      61.87      57.20          4.68      4940.54   788.14  8572.16     2.18                     BETTER
negative_control_null_effect        NaN        NaN           NaN        -7.15   -17.89     2.79    -0.00                no evidence
                   noisy_crm      56.41      50.99          5.41      5905.00  -374.62 12408.78     2.71                no evidence
        observed_confounding      62.70      58.18          4.52      5169.56  1642.40  7994.48     1.87 better but below threshold
        policy_feedback_loop      60.36      54.52          5.84      6366.70  2312.48 10591.04     2.86                     BETTER
       propensity_not_uplift      35.71      26.93          8.79      6399.32  2273.22 10324.09     2.12                     BETTER
                rare_outcome      65.11      64.86          0.25       125.78 -2047.94  2293.76     0.13                no evidence
           seasonality_trend      56.66      50.60          6.06      7506.43  2725.12 13313.24     2.77                     BETTER
              selection_bias      62.63      57.01          5.62      6125.77   783.19 12215.23     2.72                     BETTER
                      sparse      59.73      54.33          5.40      6451.24  4745.34  8094.56     2.88                     BETTER
        strong_heterogeneity      63.09      54.26          8.82     15401.90  7156.35 26485.06     5.97                     BETTER
         value_heterogeneity      52.67      49.04          3.63      7390.49 -3636.64 19174.78     2.10                no evidence
           very_rare_outcome      62.48      64.09         -1.61      -400.56 -1121.53   412.75    -0.79                no evidence
```

## RQ4  does modelling capacity change the ranking?

```
-- profit per agent-hour vs profit per lead (both analytics) --
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k   ci_low  ci_high  rel_pct                   verdict
    agent_time_heterogeneity      39.45      39.14          0.31       337.65 -1261.96  2527.06     0.16               no evidence
capacity_value_heterogeneity      31.54      31.45          0.09       195.65 -2378.01  2966.79     0.04               no evidence
               concept_drift      17.01      17.12         -0.11        -3.22    -9.65     0.00    -0.00               no evidence
            delayed_censored      40.70      40.70          0.00         0.00     0.00     0.00     0.00               no evidence
             easy_randomized      39.26      39.59         -0.34      -366.66 -1099.99     0.00    -0.18               no evidence
          hidden_confounding      35.31      35.78         -0.47      -536.25 -1608.74     0.00    -0.21               no evidence
      misleading_attribution      42.79      42.54          0.25       262.88     0.00   788.64     0.12               no evidence
negative_control_null_effect        NaN        NaN           NaN        -0.68    -1.97     0.00    -0.00               no evidence
                   noisy_crm      40.10      41.49         -1.39     -1513.27 -4539.81     0.00    -0.73               no evidence
        observed_confounding      35.31      35.78         -0.47      -536.25 -1608.74     0.00    -0.21               no evidence
        policy_feedback_loop      37.70      37.72         -0.02       -24.97   -74.91     0.00    -0.01               no evidence
       propensity_not_uplift      37.15      36.03          1.12       815.31     0.00  2108.11     0.26               no evidence
                rare_outcome      34.75      35.42         -0.67      -339.15 -1017.44     0.00    -0.40               no evidence
           seasonality_trend      38.13      38.91         -0.78      -964.18 -2892.53     0.00    -0.38               no evidence
              selection_bias      39.45      40.06         -0.62      -673.56 -1806.41    -0.44    -0.33 worse but below threshold
                      sparse      42.52      42.94         -0.42      -506.86 -1574.56   442.61    -0.24               no evidence
        strong_heterogeneity      31.13      31.59         -0.46      -810.53 -2393.06     0.00    -0.37               no evidence
         value_heterogeneity      36.52      36.52          0.00         3.71     0.00    11.02     0.00               no evidence
           very_rare_outcome      37.21      37.07          0.14        34.91     0.00   104.73     0.08               no evidence

-- value-aware allocator vs a plain sorted call list (ablation) --
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k   ci_low  ci_high  rel_pct     verdict
    agent_time_heterogeneity      58.19      43.83         14.36     16734.29 11026.26 25712.27     7.42      BETTER
capacity_value_heterogeneity      50.83      36.20         14.63     32344.71 26463.06 38226.36     6.77      BETTER
       propensity_not_uplift      37.21      36.83          0.37       286.92 -1227.49  1788.87     0.09 no evidence
                      sparse      59.98      60.59         -0.61      -759.03 -2321.88   406.53    -0.34 no evidence
         value_heterogeneity      52.46      52.84         -0.38      -837.11 -7248.49  4650.70    -0.22 no evidence
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k   ci_low  ci_high  rel_pct     verdict
    agent_time_heterogeneity      53.86      48.62          5.25      6114.61  3816.63  9436.27     2.65      BETTER
capacity_value_heterogeneity      63.69      52.76         10.93     24165.54 16159.05 33411.11     4.70      BETTER
       propensity_not_uplift      49.81      49.14          0.67       510.29  -365.74  1316.19     0.15 no evidence
                      sparse      53.64      52.96          0.68       850.87  -420.93  2270.95     0.39 no evidence
         value_heterogeneity      50.88      50.55          0.33       730.36 -1936.40  3541.80     0.19 no evidence
```

## RQ2b  causal families against the simple economic baseline

```
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k   ci_low  ci_high  rel_pct                    verdict
    agent_time_heterogeneity      60.88      57.77          3.11      3362.70  -285.93  7839.09     1.49                no evidence
capacity_value_heterogeneity      65.93      50.22         15.71     32739.46 14498.82 54223.19     6.83                     BETTER
               concept_drift      51.73      71.32        -19.58      -587.14 -1423.85   -23.50    -0.78  worse but below threshold
            delayed_censored      64.02      61.77          2.25      2459.16  1300.25  4061.22     1.07 better but below threshold
             easy_randomized      64.88      62.05          2.83      3081.50 -1313.95  8813.05     1.34                no evidence
          hidden_confounding      52.54      51.84          0.70       802.98 -2184.99  4484.32     0.30                no evidence
      misleading_attribution      60.87      61.87         -1.01     -1065.08 -3527.90  1160.57    -0.46                no evidence
negative_control_null_effect        NaN        NaN           NaN       512.80   202.75   827.25     0.32 better but below threshold
        observed_confounding      63.21      62.70          0.51       582.66 -2205.21  3546.83     0.21                no evidence
        policy_feedback_loop      61.29      60.36          0.93      1015.93 -1476.47  3713.74     0.44                no evidence
       propensity_not_uplift      54.14      35.71         18.42     13418.43 10785.06 17021.27     4.35                     BETTER
                rare_outcome      64.61      65.11         -0.49      -250.76 -1059.22   626.79    -0.25                no evidence
           seasonality_trend      60.53      56.66          3.87      4789.79   507.32 10535.78     1.72 better but below threshold
              selection_bias      62.59      62.63         -0.04       -41.20 -2268.52  2574.05    -0.02                no evidence
                      sparse      57.81      59.73         -1.92     -2290.68 -4380.28  -404.64    -0.99  worse but below threshold
        strong_heterogeneity      73.00      63.09          9.91     17307.41  8412.27 27440.15     6.33                     BETTER
         value_heterogeneity      56.55      52.67          3.88      7893.67 -2923.46 21806.53     2.20                no evidence
           very_rare_outcome      58.04      62.48         -4.44     -1101.59 -1880.39  -393.95    -2.19                      WORSE
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k    ci_low  ci_high  rel_pct                   verdict
    agent_time_heterogeneity      53.72      57.77         -4.05     -4373.90  -7605.31 -1733.54    -1.94 worse but below threshold
capacity_value_heterogeneity      60.84      50.22         10.62     22132.63  10223.11 35761.10     4.62                    BETTER
               concept_drift      35.01      71.32        -36.31     -1088.59  -2107.91  -277.49    -1.44 worse but below threshold
            delayed_censored      58.07      61.77         -3.70     -4038.06  -8500.76  1161.09    -1.75               no evidence
             easy_randomized      58.49      62.05         -3.56     -3885.32  -7115.44  -244.81    -1.68 worse but below threshold
          hidden_confounding      52.12      51.84          0.28       315.65  -2242.33  3039.70     0.12               no evidence
      misleading_attribution      57.27      61.87         -4.61     -4869.32  -9228.16  -648.21    -2.10                     WORSE
negative_control_null_effect        NaN        NaN           NaN        -1.20    -11.27     7.71    -0.00               no evidence
        observed_confounding      60.34      62.70         -2.37     -2705.46  -7541.37  1350.95    -0.96               no evidence
        policy_feedback_loop      54.05      60.36         -6.30     -6874.87 -10367.42 -3524.19    -3.00                     WORSE
       propensity_not_uplift      49.42      35.71         13.71      9984.04   6624.97 13702.26     3.24                    BETTER
                rare_outcome      54.42      65.11        -10.68     -5429.42  -8041.87 -2916.30    -5.42                     WORSE
           seasonality_trend      57.49      56.66          0.83      1030.70  -5005.20  7509.98     0.37               no evidence
              selection_bias      61.70      62.63         -0.93     -1012.74  -4230.21  2481.12    -0.44               no evidence
                      sparse      54.83      59.73         -4.90     -5851.99  -9239.59 -2139.63    -2.54                     WORSE
        strong_heterogeneity      68.30      63.09          5.21      9094.16    659.45 19747.49     3.33                    BETTER
         value_heterogeneity      50.79      52.67         -1.88     -3827.06 -17033.73 10892.68    -1.07               no evidence
           very_rare_outcome      46.45      62.48        -16.03     -3977.00  -5743.02 -2481.24    -7.92                     WORSE
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k    ci_low  ci_high  rel_pct                   verdict
    agent_time_heterogeneity      58.99      57.77          1.21      1311.61  -3286.12  6014.67     0.58               no evidence
capacity_value_heterogeneity      65.82      50.22         15.60     32503.57  19586.85 46238.50     6.78                    BETTER
               concept_drift      44.85      71.32        -26.47      -793.59  -1962.27   -26.81    -1.05 worse but below threshold
            delayed_censored      58.40      61.77         -3.37     -3671.78  -5937.59 -1197.92    -1.59 worse but below threshold
             easy_randomized      60.62      62.05         -1.43     -1558.80  -5791.07  3700.44    -0.68               no evidence
          hidden_confounding      51.84      51.84         -0.00        -4.21  -3114.95  3454.45    -0.00               no evidence
      misleading_attribution      57.17      61.87         -4.70     -4971.73  -6825.84 -3138.90    -2.14                     WORSE
negative_control_null_effect        NaN        NaN           NaN        -1.02     -7.42     3.58    -0.00               no evidence
        observed_confounding      58.47      62.70         -4.24     -4844.43 -10314.12   719.57    -1.72               no evidence
        policy_feedback_loop      53.65      60.36         -6.71     -7313.52 -11501.05 -2962.16    -3.19                     WORSE
       propensity_not_uplift      46.50      35.71         10.79      7859.27   5306.22 10228.44     2.55                    BETTER
                rare_outcome      53.35      65.11        -11.76     -5975.48  -7845.20 -4329.83    -5.96                     WORSE
           seasonality_trend      56.51      56.66         -0.15      -184.31  -4292.06  3910.65    -0.07               no evidence
              selection_bias      59.09      62.63         -3.54     -3865.95  -7257.62    33.64    -1.67               no evidence
                      sparse      54.64      59.73         -5.09     -6081.66 -11156.46 -1574.79    -2.64                     WORSE
        strong_heterogeneity      71.18      63.09          8.09     14131.92   5631.85 23893.83     5.17                    BETTER
         value_heterogeneity      52.21      52.67         -0.46      -926.62 -13252.07 13472.38    -0.26               no evidence
           very_rare_outcome      43.84      62.48        -18.64     -4623.71  -6883.75 -2459.15    -9.21                     WORSE
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k    ci_low   ci_high  rel_pct                    verdict
    agent_time_heterogeneity      52.48      57.77         -5.29     -5717.33  -9904.13  -1392.42    -2.54                      WORSE
capacity_value_heterogeneity      63.95      50.22         13.72     28601.96  14010.45  45594.64     5.97                     BETTER
               concept_drift      41.69      71.32        -29.62      -888.14  -1908.30   -144.66    -1.17  worse but below threshold
            delayed_censored      54.65      61.77         -7.12     -7764.17 -10645.61  -4160.89    -3.37                      WORSE
             easy_randomized      54.64      62.05         -7.41     -8085.70 -13566.18  -2573.30    -3.50                      WORSE
          hidden_confounding      50.01      51.84         -1.83     -2091.36  -5807.06   1072.32    -0.78                no evidence
      misleading_attribution      50.32      61.87        -11.55    -12203.74 -17495.67  -7161.91    -5.27                      WORSE
negative_control_null_effect        NaN        NaN           NaN       361.78     73.57    717.69     0.22 better but below threshold
        observed_confounding      53.44      62.70         -9.27    -10595.48 -14952.02  -5915.70    -3.76                      WORSE
        policy_feedback_loop      41.86      60.36        -18.49    -20168.81 -27132.14 -13228.97    -8.81                      WORSE
       propensity_not_uplift      42.82      35.71          7.10      5174.09   3113.87   7057.66     1.68 better but below threshold
                rare_outcome      41.81      65.11        -23.29    -11839.09 -14878.56  -9124.68   -11.81                      WORSE
           seasonality_trend      50.64      56.66         -6.02     -7448.98 -10901.35  -4292.23    -2.67                      WORSE
              selection_bias      50.56      62.63        -12.07    -13169.15 -16480.67  -9954.37    -5.69                      WORSE
                      sparse      51.48      59.73         -8.25     -9862.83 -14323.07  -5898.44    -4.28                      WORSE
        strong_heterogeneity      65.94      63.09          2.85      4976.64   -895.11  11456.92     1.82                no evidence
         value_heterogeneity      42.86      52.67         -9.80    -19954.36 -32640.78  -5733.26    -5.56                      WORSE
           very_rare_outcome      35.34      62.48        -27.14     -6732.15 -10467.65  -3290.08   -13.40                      WORSE
                       group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k    ci_low  ci_high  rel_pct                   verdict
    agent_time_heterogeneity      53.22      57.77         -4.55     -4911.60  -9264.35  -684.01    -2.18                     WORSE
capacity_value_heterogeneity      65.79      50.22         15.57     32441.62  18114.54 48162.10     6.77                    BETTER
               concept_drift      41.01      71.32        -30.31      -908.70  -1962.42   -77.55    -1.20 worse but below threshold
            delayed_censored      56.03      61.77         -5.74     -6258.45  -9925.23 -3519.51    -2.72                     WORSE
             easy_randomized      55.65      62.05         -6.40     -6983.58 -12011.36 -1938.06    -3.03                     WORSE
          hidden_confounding      49.43      51.84         -2.41     -2760.58  -6925.83   966.33    -1.02               no evidence
      misleading_attribution      54.16      61.87         -7.71     -8147.60 -11390.21 -5357.67    -3.52                     WORSE
negative_control_null_effect        NaN        NaN           NaN        42.35     -5.93   109.55     0.03               no evidence
        observed_confounding      54.94      62.70         -7.76     -8876.83 -13732.64 -3895.81    -3.15                     WORSE
        policy_feedback_loop      49.94      60.36        -10.42    -11365.30 -14871.79 -7760.41    -4.96                     WORSE
       propensity_not_uplift      45.31      35.71          9.60      6992.95   4522.58  9257.78     2.27                    BETTER
                rare_outcome      50.15      65.11        -14.95     -7600.26 -11328.75 -4293.12    -7.58                     WORSE
           seasonality_trend      52.23      56.66         -4.43     -5485.59 -11317.37  -405.97    -1.97 worse but below threshold
              selection_bias      53.62      62.63         -9.01     -9826.16 -14064.31 -6386.96    -4.25                     WORSE
                      sparse      51.41      59.73         -8.32     -9939.76 -14753.48 -5776.99    -4.32                     WORSE
        strong_heterogeneity      66.46      63.09          3.37      5884.46  -2699.64 14439.20     2.15               no evidence
         value_heterogeneity      42.98      52.67         -9.69    -19715.06 -30710.93 -8961.58    -5.50                     WORSE
           very_rare_outcome      54.95      62.48         -7.53     -1867.51  -3897.01    17.06    -3.72               no evidence
```

## RQ5  does Bayesian uncertainty pay?

```
                group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k    ci_low  ci_high  rel_pct     verdict
   hidden_confounding      48.39      53.46         -5.07     -5511.67 -18728.27  6694.87    -2.11 no evidence
propensity_not_uplift      53.75      40.00         13.75     11993.09   3282.99 20703.20     4.08      BETTER
               sparse      58.35      54.20          4.15      5966.67  -1987.88 17285.71     2.19 no evidence
    very_rare_outcome      62.53      72.03         -9.51     -1824.15  -3803.17  -211.09    -3.65       WORSE

-- Bayesian vs a bootstrapped frequentist interval --
                group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k    ci_low  ci_high  rel_pct     verdict
   hidden_confounding      48.39      53.46         -5.07     -5511.67 -18728.27  6694.87    -2.11 no evidence
propensity_not_uplift      53.75      40.00         13.75     11993.09   3282.99 20703.20     4.08      BETTER
               sparse      58.35      54.20          4.15      5966.67  -1987.88 17285.71     2.19 no evidence
    very_rare_outcome      62.53      72.03         -9.51     -1824.15  -3803.17  -211.09    -3.65       WORSE

-- risk-averse (lower credible bound) vs posterior mean --
                group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k    ci_low  ci_high  rel_pct     verdict
   hidden_confounding      47.02      48.39         -1.37     -1489.90  -7083.16  2010.90    -0.58 no evidence
propensity_not_uplift      51.79      53.75         -1.96     -1707.90  -4933.32   429.09    -0.56 no evidence
               sparse      58.42      58.35          0.07       102.15 -10115.38  7262.09     0.04 no evidence
    very_rare_outcome      62.85      62.53          0.32        62.24  -2212.85  2365.55     0.13 no evidence

-- interval honesty (empirical coverage of a stated 80% interval) --
                                       coverage_80  p_coverage_80  interval_width_80
candidate                                                                           
abl_bayes_no_hierarchy                       0.140          0.200            136.216
bayes_hierarchical                           0.227          0.359            220.732
bayes_hierarchical_abstain25                 0.227          0.359            220.732
bayes_hierarchical_abstain50                 0.227          0.359            220.732
bayes_hierarchical_lcb10                     0.227          0.359            220.732
bayes_hierarchical_lcb25                     0.227          0.359            220.732
propensity_ev_gbm_bootstrap                  0.319          0.388            280.362
propensity_ev_gbm_bootstrap_abstain25        0.319          0.388            280.362
propensity_ev_gbm_bootstrap_abstain50        0.319          0.388            280.362
propensity_ev_gbm_bootstrap_lcb10            0.319          0.388            280.362
propensity_ev_gbm_bootstrap_lcb25            0.319          0.388            280.362
```

## RQ6  hierarchical pooling vs complete pooling

```
                group  oracle%_a  oracle%_b  oracle%_diff  diff_$per1k   ci_low  ci_high  rel_pct     verdict
   hidden_confounding      48.39      45.60          2.79      3035.86 -2689.01  8760.74     1.20 no evidence
propensity_not_uplift      53.75      44.14          9.61      8378.80  1440.20 15317.40     2.81      BETTER
               sparse      58.35      48.35         10.00     14364.09  4365.49 32688.08     5.43      BETTER
    very_rare_outcome      62.53      54.39          8.13      1560.71   367.78  3176.01     3.35      BETTER
```

## RQ7  bandits vs a frozen or retrained offline model

```
regime                   concept_drift  easy_randomized  policy_feedback_loop  propensity_not_uplift   MEAN
competitor                                                                                                 
oracle                           100.0            100.0                 100.0                  100.0  100.0
retrained_propensity_ev           59.1             58.1                  58.3                   29.7   51.3
static_propensity_ev              60.1             57.5                  57.4                   29.4   51.1
bandit_thompson                   53.7             55.8                  57.0                   35.0   50.4
bandit_greedy_online              51.4             53.9                  57.1                   38.8   50.3
bandit_linucb                     50.6             52.8                  57.3                   38.2   49.7
bandit_epsilon_greedy             47.1             49.3                  53.0                   33.7   45.8
random                            22.5             25.7                  25.7                   24.1   24.5
```

## RQ8  can observational data answer causal questions?

```
regime                      easy_randomized  observed_confounding  hidden_confounding  selection_bias  policy_feedback_loop
candidate                                                                                                                  
causal_forest                          54.6                  55.0                49.2            52.7                  49.7
dr_learner                             53.8                  53.4                49.8            49.7                  42.1
hist_profit_per_agent_hour             39.6                  35.9                35.9            39.4                  38.3
lead_score_gbm                         57.8                  58.8                47.4            58.7                  55.8
propensity_ev_gbm                      62.5                  63.0                51.5            63.2                  60.9
t_learner                              58.2                  60.2                51.5            61.7                  53.3

-- PEHE (lower is better): how wrong is the estimated effect? --
regime             easy_randomized  observed_confounding  hidden_confounding  selection_bias  policy_feedback_loop
candidate                                                                                                         
causal_forest               0.0445                0.0496              0.0928          0.0587                0.0488
dr_learner                  0.0499                0.0688              0.1001          0.0674                0.1625
propensity_ev_gbm           0.0483                0.0655              0.1127          0.0757                0.0476
t_learner                   0.0888                0.1037              0.1323          0.1013                0.0935
```

## RQ9  how much data does each approach need?

```
n_config                                                 2000.0    5000.0    10000.0   25000.0   50000.0   100000.0
regime                       candidate                                                                             
capacity_value_heterogeneity dr_learner                      31.5      45.3      50.3      52.1      62.4      70.1
                             hist_profit_per_agent_hour      21.1      26.7      25.4      37.5      29.4      27.6
                             lead_score_gbm                  20.7      32.6      25.6      27.0      20.3      28.1
                             oracle                         100.0     100.0     100.0     100.0     100.0     100.0
                             propensity_ev_gbm               39.2      49.1      46.2      44.7      42.1      49.8
                             random                          25.0      25.5      29.1      21.1      22.2      20.8
                             t_learner                       26.1      48.7      44.3      53.7      60.8      69.2
propensity_not_uplift        dr_learner                      27.9      36.1      37.7      40.0      43.1      49.5
                             hist_profit_per_agent_hour      43.5      33.2      34.1      52.1      41.2      35.7
                             lead_score_gbm                  30.5      39.1      30.8      34.6      26.3      30.8
                             oracle                         100.0     100.0     100.0     100.0     100.0     100.0
                             propensity_ev_gbm               33.9      45.3      35.0      39.1      37.6      41.5
                             random                          16.0      16.8      35.0      25.8      26.0      24.9
                             t_learner                       32.6      38.5      36.8      46.9      43.7      54.2
sparse                       dr_learner                      25.9      44.7      44.0      45.0      55.2      56.2
                             hist_profit_per_agent_hour      44.3      40.1      42.0      42.1      44.5      46.0
                             lead_score_gbm                  48.2      50.0      51.7      54.3      59.9      60.0
                             oracle                         100.0     100.0     100.0     100.0     100.0     100.0
                             propensity_ev_gbm               48.4      55.0      57.6      58.7      64.9      66.0
                             random                          29.2      36.6      23.8      27.8      29.9      29.6
                             t_learner                       29.3      49.3      52.3      52.6      63.1      62.9
```

## RQ4b capacity sweep

```
capacity_ratio                                            0.05   0.10   0.25   0.50   1.00
regime                       candidate                                                    
capacity_value_heterogeneity dr_learner                   35.5   41.0   65.4   82.2   87.8
                             hist_profit_per_agent_hour    7.4   14.3   30.8   47.5   87.2
                             lead_score_gbm                4.9    9.8   23.6   52.3   87.7
                             oracle                      100.0  100.0  100.0  100.0  100.0
                             propensity_ev_gbm            26.1   34.1   48.9   67.8   84.6
                             random                        6.8   10.7   22.0   43.2   86.1
                             t_learner                    33.1   40.9   61.9   80.0   84.7
propensity_not_uplift        dr_learner                   17.8   29.9   46.4   66.4   91.6
                             hist_profit_per_agent_hour   11.8   21.2   41.8   55.9   92.3
                             lead_score_gbm                9.7   15.4   30.0   60.3   92.7
                             oracle                      100.0  100.0  100.0  100.0  100.0
                             propensity_ev_gbm            14.6   19.2   39.7   65.5   92.4
                             random                        9.1   14.3   25.2   41.9   91.3
                             t_learner                    24.9   32.6   51.2   69.3   78.7
```

## Ablations: where does the advantage come from?

```
regime                             agent_time_heterogeneity  capacity_value_heterogeneity  propensity_not_uplift  sparse  value_heterogeneity   MEAN
candidate                                                                                                                                           
oracle                                                100.0                         100.0                  100.0   100.0                100.0  100.0
t_learner                                              53.6                          62.7                   48.3    54.1                 50.4   53.8
abl_t_learner_no_value_model                           52.5                          67.4                   47.4    50.6                 48.9   53.4
propensity_ev_gbm                                      58.5                          50.0                   34.8    60.3                 53.4   51.4
abl_t_learner_no_effort_model                          49.2                          51.0                   47.4    53.7                 50.2   50.3
abl_t_learner_no_optimizer                             48.5                          51.8                   47.4    53.5                 50.3   50.3
abl_propensity_ev_no_value_model                       51.9                          59.9                   31.0    56.1                 51.2   50.0
abl_propensity_ev_no_effort_model                      45.7                          35.3                   34.9    60.7                 53.8   46.1
abl_propensity_ev_no_optimizer                         44.9                          35.1                   34.8    60.8                 54.0   45.9
hist_profit_per_agent_hour                             39.0                          30.6                   35.9    43.7                 35.4   36.9
```

## Real randomized data (OPE)

```
                       dataset  budget            candidate  dr_value  dr_ci_low  dr_ci_high  snips_value  uplift_qini_auc    dr_ess
             criteo_conversion    0.10        causal_forest     1.612      1.166       2.108        1.597            0.037 20626.867
             criteo_conversion    0.10 class_transformation     1.391      0.912       1.867        1.379           -0.020 20478.758
             criteo_conversion    0.10           dr_learner     1.642      1.092       2.250        1.602            0.048 20531.558
             criteo_conversion    0.10               random     1.410      0.809       2.060        1.401            0.046 20492.182
             criteo_conversion    0.10       response_score     1.731      1.369       2.123        1.739            0.087 20640.738
             criteo_conversion    0.10            s_learner     1.638      1.128       2.141        1.559            0.055 20544.534
             criteo_conversion    0.10            t_learner     1.760      1.367       2.185        1.701            0.090 20630.894
             criteo_conversion    0.10            x_learner     1.771      1.232       2.356        1.669            0.029 20612.548
             criteo_conversion    0.25        causal_forest     0.188     -0.226       0.655        0.191            0.037 23767.747
             criteo_conversion    0.25 class_transformation    -0.054     -0.492       0.419       -0.069           -0.020 23668.395
             criteo_conversion    0.25           dr_learner     0.027     -0.502       0.574       -0.014            0.048 23793.039
             criteo_conversion    0.25               random     0.022     -0.533       0.635        0.006            0.046 23703.432
             criteo_conversion    0.25       response_score     0.254     -0.059       0.601        0.266            0.087 23828.520
             criteo_conversion    0.25            s_learner     0.288     -0.242       0.758        0.215            0.055 23690.569
             criteo_conversion    0.25            t_learner     0.323     -0.047       0.689        0.269            0.090 23811.663
             criteo_conversion    0.25            x_learner     0.207     -0.293       0.774        0.106            0.029 23789.927
             criteo_conversion    0.50        causal_forest    -2.300     -2.746      -1.832       -2.302            0.037 32062.371
             criteo_conversion    0.50 class_transformation    -2.497     -2.911      -2.060       -2.550           -0.020 31905.987
             criteo_conversion    0.50           dr_learner    -2.365     -2.853      -1.877       -2.398            0.048 32092.397
             criteo_conversion    0.50               random    -2.291     -2.807      -1.737       -2.305            0.046 32088.349
             criteo_conversion    0.50       response_score    -2.104     -2.423      -1.778       -2.091            0.087 32073.616
             criteo_conversion    0.50            s_learner    -2.128     -2.670      -1.647       -2.213            0.055 32048.480
             criteo_conversion    0.50            t_learner    -2.039     -2.406      -1.653       -2.093            0.090 32085.545
             criteo_conversion    0.50            x_learner    -2.235     -2.748      -1.660       -2.338            0.029 31994.442
                  criteo_visit    0.10        causal_forest    44.535     42.531      46.588       44.513            0.090 20744.104
                  criteo_visit    0.10 class_transformation    43.898     42.159      45.599       43.933            0.087 20705.621
                  criteo_visit    0.10           dr_learner    43.255     41.153      45.452       43.361            0.058 20800.486
                  criteo_visit    0.10               random    37.456     34.795      40.223       37.409            0.004 20492.182
                  criteo_visit    0.10       response_score    43.573     41.882      45.230       43.944            0.090 20715.913
                  criteo_visit    0.10            s_learner    44.095     42.180      46.165       43.885            0.071 20761.556
                  criteo_visit    0.10            t_learner    44.248     42.291      46.446       43.313            0.054 20675.193
                  criteo_visit    0.10            x_learner    44.018     42.053      46.172       43.815            0.073 20739.629
                  criteo_visit    0.25        causal_forest    43.881     42.100      45.672       43.821            0.090 23930.111
                  criteo_visit    0.25 class_transformation    43.939     42.587      45.434       44.238            0.087 23908.373
                  criteo_visit    0.25           dr_learner    42.263     40.200      44.350       42.569            0.058 23985.572
                  criteo_visit    0.25               random    37.462     34.957      40.026       37.419            0.004 23703.432
                  criteo_visit    0.25       response_score    44.052     42.781      45.446       44.557            0.090 23927.894
                  criteo_visit    0.25            s_learner    43.189     41.575      45.142       43.347            0.071 23942.984
                  criteo_visit    0.25            t_learner    43.244     41.432      45.151       42.329            0.054 23864.009
                  criteo_visit    0.25            x_learner    43.320     41.563      45.245       43.304            0.073 23879.537
                  criteo_visit    0.50        causal_forest    41.734     40.019      43.471       42.138            0.090 32109.751
                  criteo_visit    0.50 class_transformation    41.637     40.305      42.947       42.186            0.087 32091.675
                  criteo_visit    0.50           dr_learner    40.229     38.369      42.244       40.713            0.058 32207.042
                  criteo_visit    0.50               random    37.366     35.278      39.506       37.346            0.004 32088.349
                  criteo_visit    0.50       response_score    41.648     40.451      42.877       42.326            0.090 32135.740
                  criteo_visit    0.50            s_learner    40.876     39.307      42.652       41.218            0.071 32085.888
                  criteo_visit    0.50            t_learner    40.957     39.215      42.908       40.271            0.054 32095.766
                  criteo_visit    0.50            x_learner    40.978     39.241      42.798       41.121            0.073 32108.065
hillstrom_any_email_conversion    0.10        causal_forest     5.238      3.875       6.676        5.155            0.020 11190.695
hillstrom_any_email_conversion    0.10 class_transformation     5.174      3.805       6.624        5.095            0.000 11188.333
hillstrom_any_email_conversion    0.10           dr_learner     5.758      4.337       7.320        5.610            0.021 11191.286
hillstrom_any_email_conversion    0.10               random     5.007      3.689       6.356        4.986            0.002 11162.327
hillstrom_any_email_conversion    0.10       response_score     5.584      4.219       7.091        5.629            0.007 11209.610
hillstrom_any_email_conversion    0.10            s_learner     5.258      3.919       6.720        5.117           -0.005 11200.151
hillstrom_any_email_conversion    0.10            t_learner     5.141      3.727       6.644        5.008           -0.008 11177.694
hillstrom_any_email_conversion    0.10            x_learner     5.455      4.049       6.921        5.280           -0.031 11191.286
hillstrom_any_email_conversion    0.25        causal_forest     4.646      3.292       6.201        4.557            0.020 12159.083
hillstrom_any_email_conversion    0.25 class_transformation     4.714      3.305       6.107        4.629            0.000 12142.919
hillstrom_any_email_conversion    0.25           dr_learner     5.015      3.624       6.485        4.917            0.021 12184.229
hillstrom_any_email_conversion    0.25               random     4.461      3.131       5.850        4.440            0.002 12169.859
hillstrom_any_email_conversion    0.25       response_score     4.697      3.357       6.111        4.717            0.007 12126.156
hillstrom_any_email_conversion    0.25            s_learner     4.666      3.315       6.123        4.527           -0.005 12181.833
hillstrom_any_email_conversion    0.25            t_learner     4.390      2.983       5.813        4.247           -0.008 12153.695
hillstrom_any_email_conversion    0.25            x_learner     4.300      2.984       5.737        4.236           -0.031 12144.116
hillstrom_any_email_conversion    0.50        causal_forest     3.580      2.184       5.025        3.443            0.020 14165.383
hillstrom_any_email_conversion    0.50 class_transformation     3.422      2.027       4.952        3.358            0.000 14209.219
hillstrom_any_email_conversion    0.50           dr_learner     3.547      2.219       5.002        3.390            0.021 14234.691
hillstrom_any_email_conversion    0.50               random     3.385      2.086       4.783        3.360            0.002 14178.415
hillstrom_any_email_conversion    0.50       response_score     3.247      1.906       4.639        3.264            0.007 14178.412
hillstrom_any_email_conversion    0.50            s_learner     3.356      2.019       4.783        3.180           -0.005 14308.154
hillstrom_any_email_conversion    0.50            t_learner     3.328      1.882       4.823        3.173           -0.008 14201.514
hillstrom_any_email_conversion    0.50            x_learner     2.696      1.447       4.153        2.629           -0.031 14225.212
     hillstrom_any_email_visit    0.10        causal_forest   111.647    106.017     117.349      111.150            0.018 11211.384
     hillstrom_any_email_visit    0.10 class_transformation   112.039    106.465     117.983      111.770            0.015 11206.653
     hillstrom_any_email_visit    0.10           dr_learner   113.234    107.519     119.331      112.950            0.023 11201.338
     hillstrom_any_email_visit    0.10               random   110.394    104.779     115.743      110.184           -0.002 11162.327
     hillstrom_any_email_visit    0.10       response_score   111.578    106.084     117.599      111.712            0.019 11228.521
     hillstrom_any_email_visit    0.10            s_learner   112.395    106.709     118.232      112.338            0.021 11252.757
     hillstrom_any_email_visit    0.10            t_learner   113.385    107.774     119.450      113.353            0.012 11247.437
     hillstrom_any_email_visit    0.10            x_learner   113.590    108.015     119.453      113.502            0.023 11188.924
     hillstrom_any_email_visit    0.25        causal_forest   122.823    117.233     128.551      122.324            0.018 12193.209
     hillstrom_any_email_visit    0.25 class_transformation   122.254    116.966     128.186      121.843            0.015 12192.610
     hillstrom_any_email_visit    0.25           dr_learner   122.075    116.372     127.943      121.558            0.023 12196.202
     hillstrom_any_email_visit    0.25               random   118.449    113.073     124.030      118.374           -0.002 12169.859
     hillstrom_any_email_visit    0.25       response_score   120.611    115.217     125.810      120.939            0.019 12208.774
     hillstrom_any_email_visit    0.25            s_learner   121.962    116.195     127.351      121.829            0.021 12218.353
     hillstrom_any_email_visit    0.25            t_learner   121.393    115.656     126.945      121.118            0.012 12194.407
     hillstrom_any_email_visit    0.25            x_learner   122.236    116.442     127.866      121.739            0.023 12232.124
     hillstrom_any_email_visit    0.50        causal_forest   136.485    130.937     141.854      136.204            0.018 14245.352
     hillstrom_any_email_visit    0.50 class_transformation   135.130    129.989     140.309      134.851            0.015 14217.510
     hillstrom_any_email_visit    0.50           dr_learner   136.802    131.150     142.574      136.380            0.023 14272.011
     hillstrom_any_email_visit    0.50               random   130.363    124.730     135.571      130.293           -0.002 14178.415
     hillstrom_any_email_visit    0.50       response_score   134.977    129.835     140.095      135.291            0.019 14241.213
     hillstrom_any_email_visit    0.50            s_learner   136.075    130.436     141.418      136.018            0.021 14222.246
     hillstrom_any_email_visit    0.50            t_learner   133.844    128.076     139.051      133.685            0.012 14208.028
     hillstrom_any_email_visit    0.50            x_learner   135.291    130.013     140.635      134.833            0.023 14251.872
     hillstrom_mens_conversion    0.10        causal_forest     5.257      3.839       6.849        5.151            0.010 10669.667
     hillstrom_mens_conversion    0.10 class_transformation     5.062      3.321       6.929        5.198           -0.024 10685.000
     hillstrom_mens_conversion    0.10           dr_learner     5.672      4.213       7.258        5.471           -0.008 10631.000
     hillstrom_mens_conversion    0.10               random     5.725      4.289       7.257        5.727           -0.001 10656.333
     hillstrom_mens_conversion    0.10       response_score     5.755      4.286       7.484        5.758            0.019 10657.000
     hillstrom_mens_conversion    0.10            s_learner     5.905      4.474       7.551        5.717           -0.023 10633.667
     hillstrom_mens_conversion    0.10            t_learner     5.952      4.353       7.710        5.724           -0.003 10658.333
     hillstrom_mens_conversion    0.10            x_learner     5.570      4.166       7.194        5.367           -0.004 10639.667
     hillstrom_mens_conversion    0.25        causal_forest     4.888      3.356       6.633        4.838            0.010 10637.000
     hillstrom_mens_conversion    0.25 class_transformation     5.143      3.240       7.255        5.018           -0.024 10648.333
     hillstrom_mens_conversion    0.25           dr_learner     5.150      3.574       6.845        5.025           -0.008 10604.333
     hillstrom_mens_conversion    0.25               random     5.370      3.758       7.084        5.370           -0.001 10671.667
     hillstrom_mens_conversion    0.25       response_score     5.223      3.734       6.994        5.218            0.019 10668.333
     hillstrom_mens_conversion    0.25            s_learner     5.470      3.803       7.290        5.299           -0.023 10615.000
     hillstrom_mens_conversion    0.25            t_learner     5.264      3.624       7.058        5.048           -0.003 10649.667
     hillstrom_mens_conversion    0.25            x_learner     5.556      3.888       7.380        5.330           -0.004 10647.000
     hillstrom_mens_conversion    0.50        causal_forest     4.207      2.416       6.100        4.287            0.010 10626.000
     hillstrom_mens_conversion    0.50 class_transformation     3.782      1.735       5.717        3.672           -0.024 10611.333
     hillstrom_mens_conversion    0.50           dr_learner     4.503      2.775       6.375        4.371           -0.008 10707.333
     hillstrom_mens_conversion    0.50               random     4.130      2.420       6.095        4.130           -0.001 10625.333
     hillstrom_mens_conversion    0.50       response_score     4.550      2.751       6.454        4.546            0.019 10645.333
     hillstrom_mens_conversion    0.50            s_learner     3.888      2.191       5.866        3.713           -0.023 10593.333
     hillstrom_mens_conversion    0.50            t_learner     4.237      2.478       6.122        4.015           -0.003 10645.333
     hillstrom_mens_conversion    0.50            x_learner     4.487      2.794       6.343        4.267           -0.004 10613.333
          hillstrom_mens_visit    0.10        causal_forest   115.982    109.938     122.062      115.215            0.004 10697.000
          hillstrom_mens_visit    0.10 class_transformation   114.902    109.156     120.885      114.380           -0.008 10673.000
          hillstrom_mens_visit    0.10           dr_learner   116.994    111.065     123.182      116.481            0.001 10665.000
          hillstrom_mens_visit    0.10               random   114.543    108.473     120.320      114.548            0.003 10656.333
          hillstrom_mens_visit    0.10       response_score   115.829    110.007     121.609      116.215            0.023 10721.667
          hillstrom_mens_visit    0.10            s_learner   115.272    109.254     121.123      115.178            0.005 10700.333
          hillstrom_mens_visit    0.10            t_learner   114.506    108.562     120.589      114.278            0.002 10708.333
          hillstrom_mens_visit    0.10            x_learner   117.059    111.018     122.706      116.388            0.007 10684.333
          hillstrom_mens_visit    0.25        causal_forest   125.714    119.474     131.851      124.983            0.004 10711.667
          hillstrom_mens_visit    0.25 class_transformation   125.033    118.751     131.787      124.413           -0.008 10650.333
          hillstrom_mens_visit    0.25           dr_learner   127.196    121.155     133.965      126.610            0.001 10716.333
          hillstrom_mens_visit    0.25               random   124.382    118.087     130.667      124.408            0.003 10671.667
          hillstrom_mens_visit    0.25       response_score   127.390    121.054     133.662      127.909            0.023 10744.333
          hillstrom_mens_visit    0.25            s_learner   127.013    120.777     133.218      127.318            0.005 10721.667
          hillstrom_mens_visit    0.25            t_learner   126.563    120.128     133.197      126.273            0.002 10707.667
          hillstrom_mens_visit    0.25            x_learner   128.869    122.288     135.844      128.300            0.007 10698.333
          hillstrom_mens_visit    0.50        causal_forest   141.833    135.363     148.840      141.357            0.004 10754.667
          hillstrom_mens_visit    0.50 class_transformation   139.903    133.486     146.633      139.314           -0.008 10676.000
          hillstrom_mens_visit    0.50           dr_learner   141.333    134.747     147.857      140.734            0.001 10718.000
          hillstrom_mens_visit    0.50               random   141.589    135.017     148.343      141.598            0.003 10625.333
          hillstrom_mens_visit    0.50       response_score   145.010    138.351     151.476      145.367            0.023 10714.000
          hillstrom_mens_visit    0.50            s_learner   142.094    135.441     148.798      142.254            0.005 10748.000
          hillstrom_mens_visit    0.50            t_learner   142.875    136.352     149.300      142.573            0.002 10731.333
          hillstrom_mens_visit    0.50            x_learner   141.952    135.489     148.733      140.999            0.007 10756.667
   hillstrom_womens_conversion    0.10        causal_forest     5.359      3.846       6.907        5.531            0.076 10608.000
   hillstrom_womens_conversion    0.10 class_transformation     4.626      2.785       6.462        5.093            0.013 10638.000
   hillstrom_womens_conversion    0.10           dr_learner     5.617      3.972       7.279        5.793            0.065 10625.333
   hillstrom_womens_conversion    0.10               random     5.069      3.644       6.522        5.055           -0.014 10612.667
   hillstrom_womens_conversion    0.10       response_score     5.491      3.938       7.050        5.456           -0.069 10619.333
   hillstrom_womens_conversion    0.10            s_learner     5.001      3.469       6.546        5.002           -0.016 10636.000
   hillstrom_womens_conversion    0.10            t_learner     5.147      3.597       6.721        5.289            0.009 10630.000
   hillstrom_womens_conversion    0.10            x_learner     5.234      3.641       6.845        5.453            0.073 10592.000
   hillstrom_womens_conversion    0.25        causal_forest     4.941      3.248       6.629        5.027            0.076 10674.667
   hillstrom_womens_conversion    0.25 class_transformation     3.329      1.375       5.256        3.934            0.013 10674.667
   hillstrom_womens_conversion    0.25           dr_learner     4.857      3.227       6.546        4.939            0.065 10633.333
   hillstrom_womens_conversion    0.25               random     4.258      2.832       5.860        4.221           -0.014 10702.667
   hillstrom_womens_conversion    0.25       response_score     3.615      2.258       4.996        3.572           -0.069 10616.000
   hillstrom_womens_conversion    0.25            s_learner     3.897      2.340       5.280        3.884           -0.016 10620.667
   hillstrom_womens_conversion    0.25            t_learner     4.038      2.508       5.546        4.169            0.009 10654.667
   hillstrom_womens_conversion    0.25            x_learner     4.474      2.961       6.151        4.625            0.073 10634.000
   hillstrom_womens_conversion    0.50        causal_forest     2.931      1.296       4.590        3.006            0.076 10703.000
   hillstrom_womens_conversion    0.50 class_transformation     1.990     -0.085       3.971        2.448            0.013 10695.667
   hillstrom_womens_conversion    0.50           dr_learner     2.713      1.096       4.357        2.708            0.065 10679.667
   hillstrom_womens_conversion    0.50               random     2.033      0.599       3.602        1.999           -0.014 10712.333
   hillstrom_womens_conversion    0.50       response_score     1.457      0.037       2.975        1.394           -0.069 10631.667
   hillstrom_womens_conversion    0.50            s_learner     1.967      0.370       3.569        1.902           -0.016 10720.333
   hillstrom_womens_conversion    0.50            t_learner     1.941      0.330       3.520        2.027            0.009 10719.000
   hillstrom_womens_conversion    0.50            x_learner     3.083      1.556       4.842        3.227            0.073 10696.333
        hillstrom_womens_visit    0.10        causal_forest   112.981    107.202     118.742      113.303            0.060 10645.333
        hillstrom_womens_visit    0.10 class_transformation   110.794    105.023     116.711      111.452            0.019 10648.000
        hillstrom_womens_visit    0.10           dr_learner   112.562    106.718     118.529      113.138            0.061 10623.333
        hillstrom_womens_visit    0.10               random   108.909    103.159     114.395      108.801            0.002 10612.667
        hillstrom_womens_visit    0.10       response_score   112.964    106.954     118.490      113.159            0.014 10610.000
        hillstrom_womens_visit    0.10            s_learner   112.605    106.771     118.200      113.151            0.047 10616.000
        hillstrom_womens_visit    0.10            t_learner   110.811    105.083     116.716      111.896            0.029 10662.667
        hillstrom_womens_visit    0.10            x_learner   112.069    106.291     117.773      112.659            0.053 10644.000
        hillstrom_womens_visit    0.25        causal_forest   122.523    116.459     128.267      122.883            0.060 10689.333
        hillstrom_womens_visit    0.25 class_transformation   117.318    111.175     123.338      117.975            0.019 10655.333
        hillstrom_womens_visit    0.25           dr_learner   122.584    116.372     128.834      122.862            0.061 10688.667
        hillstrom_womens_visit    0.25               random   116.570    110.378     122.370      116.551            0.002 10702.667
        hillstrom_womens_visit    0.25       response_score   117.493    111.553     123.379      117.640            0.014 10601.333
        hillstrom_womens_visit    0.25            s_learner   121.836    115.547     127.776      122.559            0.047 10709.333
        hillstrom_womens_visit    0.25            t_learner   119.291    113.305     125.537      120.134            0.029 10666.000
        hillstrom_womens_visit    0.25            x_learner   121.706    115.733     127.771      122.074            0.053 10687.333
        hillstrom_womens_visit    0.50        causal_forest   137.337    130.536     144.147      137.140            0.060 10717.000
        hillstrom_womens_visit    0.50 class_transformation   125.489    119.265     131.446      126.295            0.019 10701.000
        hillstrom_womens_visit    0.50           dr_learner   136.655    130.481     143.650      136.221            0.061 10697.000
        hillstrom_womens_visit    0.50               random   123.669    117.022     129.640      123.632            0.002 10712.333
        hillstrom_womens_visit    0.50       response_score   125.559    119.564     131.699      125.906            0.014 10661.667
        hillstrom_womens_visit    0.50            s_learner   135.040    128.500     142.043      134.915            0.047 10730.333
        hillstrom_womens_visit    0.50            t_learner   129.898    123.474     136.443      130.034            0.029 10758.333
        hillstrom_womens_visit    0.50            x_learner   134.648    127.947     141.277      134.663            0.053 10714.333
```

## MMM track

```
                regime                     candidate  roi_mape  roi_rank_spearman  regret_pct_b0.7  regret_pct_b1.0  regret_pct_b1.5
 mmm_high_collinearity              equal_allocation      1.00              -0.70             9.84             6.13             3.67
 mmm_high_collinearity                     naive_ols      1.68               0.04            82.13            84.27            86.24
 mmm_high_collinearity                        oracle      0.03               1.00             0.00             0.00             0.00
 mmm_high_collinearity            pymc_marketing_mmm      2.58              -0.62             8.77             3.86             2.22
 mmm_high_collinearity pymc_marketing_mmm_calibrated      0.28               0.05            13.50             3.38             4.70
 mmm_high_collinearity                 reported_roas      0.61               0.70            91.48            92.69            93.65
 mmm_high_collinearity      ridge_adstock_saturation      0.92               0.28             5.17             3.75             2.77
      mmm_long_history              equal_allocation      1.00              -0.70             9.97             6.21             3.72
      mmm_long_history                     naive_ols      0.76               0.13            82.99            85.25            87.19
      mmm_long_history                        oracle      0.04               1.00             0.00             0.00             0.00
      mmm_long_history            pymc_marketing_mmm      0.85               0.30            50.93            52.76            36.82
      mmm_long_history pymc_marketing_mmm_calibrated      0.20               0.55            33.40            25.13            11.06
      mmm_long_history                 reported_roas      0.60               0.70            91.44            92.66            93.63
      mmm_long_history      ridge_adstock_saturation      1.24              -0.37             5.25             2.92             2.95
        mmm_low_signal              equal_allocation      1.00              -0.70             9.93             6.19             3.70
        mmm_low_signal                     naive_ols      1.24               0.08            82.07            84.21            86.19
        mmm_low_signal                        oracle      0.04               1.00             0.00             0.00             0.00
        mmm_low_signal            pymc_marketing_mmm      1.41              -0.45            15.66             6.26             3.03
        mmm_low_signal pymc_marketing_mmm_calibrated      0.22               0.45             3.16             1.62             2.29
        mmm_low_signal                 reported_roas      0.60               0.70            91.45            92.67            93.63
        mmm_low_signal      ridge_adstock_saturation      0.81               0.02            13.23             6.54             5.02
 mmm_smb_short_history              equal_allocation      1.00              -0.70             9.82             6.12             3.66
 mmm_smb_short_history                     naive_ols      1.28              -0.52            86.30            87.73            89.14
 mmm_smb_short_history                        oracle      0.04               1.00             0.00             0.00             0.00
 mmm_smb_short_history            pymc_marketing_mmm      1.71              -0.40            12.50             4.94             1.75
 mmm_smb_short_history pymc_marketing_mmm_calibrated      0.28               0.32             1.62             0.61             1.75
 mmm_smb_short_history                 reported_roas      0.60               0.70            91.49            92.69            93.65
 mmm_smb_short_history      ridge_adstock_saturation      1.29              -0.55             7.25             5.96             6.13
          mmm_standard              equal_allocation      1.00              -0.70             9.93             6.19             3.70
          mmm_standard                     naive_ols      0.70              -0.01            82.07            84.21            86.19
          mmm_standard                        oracle      0.04               1.00             0.00             0.00             0.00
          mmm_standard            pymc_marketing_mmm      1.04              -0.30            19.72            15.50             7.10
          mmm_standard pymc_marketing_mmm_calibrated      0.21               0.55             7.61             3.43             3.52
          mmm_standard                 reported_roas      0.60               0.70            91.45            92.67            93.63
          mmm_standard      ridge_adstock_saturation      0.63               0.27             3.03             2.73             2.96
mmm_very_short_history              equal_allocation      1.00              -0.70             9.81             6.11             3.66
mmm_very_short_history                     naive_ols      1.28              -0.04            77.92            80.34            82.68
mmm_very_short_history                        oracle      0.05               1.00             0.00             0.00             0.00
mmm_very_short_history            pymc_marketing_mmm      2.42              -0.37            16.77             5.85             2.48
mmm_very_short_history pymc_marketing_mmm_calibrated      0.30               0.42             6.93             1.25             1.81
mmm_very_short_history                 reported_roas      0.61               0.68            91.49            92.69            93.65
mmm_very_short_history      ridge_adstock_saturation      0.74              -0.52             5.91             1.98             1.88
```

## Data-regime map: what wins where

```
                      regime              winner  winner_oracle%         best_analytics  analytics_oracle%  gap_pts  gap_$per1k                    verdict
    agent_time_heterogeneity propensity_ev_logit            61.3   hist_conversion_rate               41.4     19.8     21310.0                     BETTER
capacity_value_heterogeneity           x_learner            64.9   hist_conversion_rate               32.7     32.2     70709.0                     BETTER
               concept_drift                fifo          1453.9                   fifo             1453.9      0.0         0.0                no evidence
            delayed_censored propensity_ev_logit            65.9   hist_conversion_rate               42.7     23.2     24409.0                     BETTER
             easy_randomized propensity_ev_logit            65.7   hist_conversion_rate               42.5     23.2     24550.0                     BETTER
          hidden_confounding propensity_ev_logit            54.8 existing_policy_capped               47.3      7.5      9936.0                     BETTER
      misleading_attribution propensity_ev_logit            65.8   hist_conversion_rate               43.1     22.7     23447.0                     BETTER
negative_control_null_effect           s_learner             NaN             lowest_cpl                NaN      NaN       496.0 better but below threshold
                   noisy_crm propensity_ev_logit            59.9   hist_conversion_rate               41.4     18.5     19577.0                     BETTER
        observed_confounding propensity_ev_logit            64.7 existing_policy_capped               47.3     17.4     20454.0                     BETTER
        policy_feedback_loop propensity_ev_logit            63.5   hist_conversion_rate               39.5     23.9     25971.0                     BETTER
       propensity_not_uplift           s_learner            52.4   hist_conversion_rate               40.1     12.3      9770.0                     BETTER
                rare_outcome    lead_score_logit            73.7   hist_conversion_rate               37.9     35.8     16042.0                     BETTER
           seasonality_trend           s_learner            59.8   hist_conversion_rate               41.3     18.5     23668.0                     BETTER
              selection_bias propensity_ev_logit            65.9 existing_policy_capped               47.3     18.6     19598.0                     BETTER
                      sparse propensity_ev_logit            63.8   hist_conversion_rate               43.8     20.0     23735.0                     BETTER
        strong_heterogeneity           s_learner            72.8        hist_net_profit               31.6     41.3     72285.0                     BETTER
         value_heterogeneity propensity_ev_logit            56.4   hist_conversion_rate               40.1     16.3     28890.0                     BETTER
           very_rare_outcome    lead_score_logit            70.2   hist_conversion_rate               37.5     32.7      8355.0                     BETTER

NOTE: both `winner` and `best_analytics` are post-hoc maxima over candidates, so the gap is optimistic on both sides and this table is DESCRIPTIVE. The preregistered comparisons against fixed references (hist_profit_per_agent_hour, lead_score_gbm, propensity_ev_gbm) in the RQ sections above are the ones that decide anything.
```

## Cost of the win: value against compute

```
                            pct_of_oracle_incremental  fit_seconds  predict_seconds  peak_rss_delta_mb  fit_x_vs_propensity_ev
candidate                                                                                                                     
dr_learner                                     125.81         5.46             0.23               0.00                    3.19
causal_forest                                  122.67        21.83             1.08               1.28                   12.74
x_learner                                      110.19         4.07             0.52               0.00                    2.37
s_learner                                      109.81         2.21             0.32               0.00                    1.29
propensity_ev_logit                            106.38         0.98             0.18               0.55                    0.57
fifo                                           105.14         0.04             0.00               0.00                    0.03
existing_policy_replay                         104.47         0.00             0.00                NaN                    0.00
propensity_ev_gbm                              104.06         1.71             0.26               0.00                    1.00
funnel_ev_gbm                                  103.85         3.12             0.55               0.00                    1.82
oracle                                         100.00         0.00             0.00               0.01                    0.00
random                                          98.71         0.04             0.00               0.00                    0.03
class_transformation                            95.99         2.28             0.26               0.00                    1.33
existing_policy_capped                          93.90         0.00             0.00                NaN                    0.00
t_learner                                       91.25         2.42             0.31               0.00                    1.41
call_everyone                                   89.67         0.04             0.01               0.00                    0.02
lead_score_logit                                86.35         0.96             0.17               0.18                    0.56
lead_score_gbm                                  83.41         1.67             0.21               0.00                    0.98
lowest_cpl                                      81.02         0.04             0.00               0.00                    0.03
last_click_attribution                          73.52         0.05             0.00               0.01                    0.03
hist_conversion_rate                            56.31         0.05             0.00               0.00                    0.03
hist_roas                                       54.94         0.05             0.00               0.00                    0.03
hist_net_profit                                 54.78         0.05             0.00               0.06                    0.03
hist_profit_per_agent_hour                      54.55         0.06             0.00               0.00                    0.03
do_nothing                                       0.00         0.00             0.00               0.00                    0.00
```
