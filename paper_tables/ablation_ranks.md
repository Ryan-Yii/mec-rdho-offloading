| algorithm                                |   mean_rank |   rank_order |   n_paired_scenarios | metric   | paired_key                 |
|:-----------------------------------------|------------:|-------------:|---------------------:|:---------|:---------------------------|
| RDHO-core                                |     4.33333 |            5 |                   30 | fitness  | scenario_id + replicate_id |
| RDHO-core w/o hybrid RIME-DBO fusion     |     3.2     |            2 |                   30 | fitness  | scenario_id + replicate_id |
| RDHO-core w/o dual-source initialization |     7       |            7 |                   30 | fitness  | scenario_id + replicate_id |
| RDHO-core w/o adaptive role allocation   |     4.36667 |            6 |                   30 | fitness  | scenario_id + replicate_id |
| RDHO-core w/o elite preservation         |     4.06667 |            4 |                   30 | fitness  | scenario_id + replicate_id |
| RDHO-core w/o dynamic penalty            |     3.83333 |            3 |                   30 | fitness  | scenario_id + replicate_id |
| RDHO-full                                |     1.2     |            1 |                   30 | fitness  | scenario_id + replicate_id |