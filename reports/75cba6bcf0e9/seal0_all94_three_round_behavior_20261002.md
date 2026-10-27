# SEAL-0 全94题：三轮合并后的性能、成本分布与重复波动

采用用户指定的全94题口径：H历史首轮＋R1/R2两次补跑。保留未修改的原生评分、源run与归档；本分析零agent调用、零评分调用。

**合并现象：平均原生性能近持平；平均token也接近，但典型题与P95更贵、最极端尾部较短；同题重跑的相对波动基本相同，逐题成本差方向经常改变。** 变差同样是结果，不以显著提升作为分析或写作前提。

## 覆盖与统计单位

94题全部进入整体统计，86题三轮完整、6题有两轮、2题只有历史首轮，合计272个配对题目轮次、544次正常执行。缺失轮次不记0，不补造结果。仅有首轮的q6/q96不能衡量重复波动；92道有重复记录的题用于重复性分析。q38/q55/q62/q100缺R2，q87/q92缺R1。

每题先对其可用配对轮次取均值，再让94题等权；不能按544次执行独立加权。旧N额外轮次继续保留在此前留档，此报告为指定的H/R1/R2目标，不将它混为第四轮。区间按题bootstrap，30,000次，seed=20261002。

## 性能现象

全94题等权原生正确率：BASE 35.6%，V2 35.5%，V2−BASE -0.18个百分点，接近持平。逐题平均标签较好20题、较差20题、相同54题。原生差值区间约[-6.4,+5.7]个百分点，只说明观察稳定程度，不抹去正负方向结果。

三轮完整86题差值约−1.94个百分点；沿用此前q5/q13对称剔除口径，全92题差值约−1.63个百分点。此前较早33题三轮是+5.05个百分点，剩余完整53题三轮是−6.29个百分点；这些是样本异质性与历史协议/时间变化混合的观察，不应只保留正结果或只用某个负子集代表全94题。

## Token分布：每题可用轮次均值，94题等权

| 指标 | BASE | V2 |
|---|---:|---:|
| 均值（万token） | 89.5 | 88.3 |
| 中位数（万token） | 31.1 | 32.9 |
| P90（万token） | 204.0 | 222.4 |
| P95（万token） | 340.0 | 401.4 |
| P99（万token） | 875.5 | 513.8 |
| 最大题目均值（万token） | 956.5 | 563.6 |
| 标准差（万token） | 152.1 | 120.8 |
| 最耗token的10题占总量 | 51.6% | 47.0% |

均值仅下降约1.3%，但中位数增加约5.9%，P95增加约18.1%；P99下降约41.3%。V2逐题均值更耗56题、更省38题，每题消耗比的中位数为1.063。平均配对差仅-1.2万，但逐题绝对差平均50.7万：小的净差与大的局部变化同时存在，尚不能把局部差额全部归为V2真实效应。

这不是统一收窄到一个低成本区间：最极端尾部缩短，同时典型题与中高成本区间上移。原始标准差下降包含尾部贡献，不能单独替代同题重复稳定性指标。Token包括重复上下文与输出，不含评分；总token不是美元费用。

## 同题重复：92道有重复记录题，包含三轮所有两两比较

| 指标 | BASE | V2 |
|---|---:|---:|
| 每题最大/最小token倍数的中位数 | 3.20 | 2.87 |
| 最大/最小超过2倍的题数 | 57 | 56 |
| 最大/最小超过4倍的题数 | 38 | 36 |
| 两两绝对对数token差，先题内再题间平均 | 0.856 | 0.836 |
| 题内对数token样本方差，题间均值 | 0.775 | 0.769 |
| 至少一次原生对错变化的题数 | 31 | 30 |
| 两两标签不一致率，先题内再题间平均 | 22.8% | 22.5% |

相对token波动V2/BASE约0.977，仅小约2.3%；区间[0.816,1.165]。题内对数方差比约0.992，几乎相同。因此全样本现象是两臂都高度波动，V2没有明显把这种波动收束。最大/最小倍数使用两到三次观测，不能直接与此前两次观测倍数比较。

至少一臂出现跨轮标签变化的题共46道，约占92题的一半。V2标签两两不一致率略低约0.36个百分点，观察上也是近持平。

## 成本差方向是否稳定？

有重复的92题中，V2在所有可用轮次都更耗24题、都更省8题；60题既出现更耗也出现更省。不是所有题都被一致推向某个成本方向。

| 比较轮次 | 共同题数 | 逐题log(V2/BASE)相关 |
|---|---:|---:|
| H vs R1 | 90 | -0.000 |
| H vs R2 | 88 | -0.128 |
| R1 vs R2 | 86 | -0.076 |

这些相关接近零或略负，说明某轮差异大不意味着另外一轮仍差异大；绝对题目难度造成的成本可预测性与干预差额可重复性是不同问题。历史与新轮协议差异也会贡献这一现象，因此这里只报告观测，不把全部变动称作纯随机性。

## 工具行为

工具同样每题先平均可用轮次，然后94题等权，以下是每题平均次数。

| 指标/工具 | BASE | V2 |
|---|---:|---:|
| llm_calls | 20.97 | 20.73 |
| tool_calls | 8.39 | 10.97 |
| search_calls | 5.87 | 7.37 |
| agent_nodes | 5.09 | 4.76 |
| actual_max_depth | 0.81 | 0.74 |
| web_search | 5.81 | 7.18 |
| list_files | 0.42 | 0.75 |
| search_files | 0.06 | 0.19 |
| run_python_code | 0.81 | 1.61 |
| save_file | 0.12 | 0.09 |

## 逐题正负结果与噪声参照

表现较差的20题中，12题V2同时更耗token；表现较好的20题中，10题V2更耗。性能平均标签相同的54题中，34题V2更耗。成本与评分的变化不是统一的收益关系。

q54三轮BASE全部判对、V2全部判错，是清楚的重复负面观察，应直接报告。q62两个可用轮次V2全部判对、BASE全部判错，但缺R2，不能写成三轮重复正面。相对性能方向反转5题仍是q65、q68、q71、q103、q110。原生口径不改。

92题的跨条件标签不一致率约23.9%，同条件重复约22.6%，差额约1.21个百分点。此差不是准确率收益；在独立、稳定重复假设下可作为逐题成功概率差平方的噪声参照，区间约[-2.2,+5.2]个百分点。采用同轮配对差额的重复方差作校正得到另一诊断，保存在JSON；这些方法不是对每道题因果贡献的精确分解。

**认识：平均性能近持平不等于轨迹不变；相反，资源投入发生双向重分配，部分题更费资源且表现更差，另一部分表现更好。远端长尾缩短与典型题成本上升并存，同题重复波动仍大。** 这些正负现象都值得报告，而不需要先证明V2高或低才能构成结果。

因果归因与跨总体推广仍受缺失执行、有限重复、原生评分口径和历史协议/时间差异限制。区间用于说明估计稳定程度，不把“区间跨0”当作没有现象，也不把“观察到分布变化”当作已经证明组织信息的稳定因果机制。

## 全94题逐题记录

序列H→R1→R2；“缺”表示该轮没有正常完成的双臂配对，不表示0分。

| 题目 | 可用轮数 | BASE标签序列 | V2标签序列 | BASE/V2每题token均值（万） | V2−BASE平均标签 |
|---|---:|---|---|---:|---:|
| q1：How many volcanic eruptions in the 21st century have produced a plume height of at least 18 miles? | 3 | 0→1→0 | 0→0→0 | 56.2 / 218.0 | -0.333 |
| q2：Which was the third Asian country to report a case of clade Ib mpox during the most recent outbreak? | 3 | 1→1→1 | 1→1→1 | 11.6 / 81.3 | +0.000 |
| q3：What is the current age of the last American experimental physicist to win the Nobel Prize in Physics? | 3 | 0→0→0 | 0→0→0 | 188.6 / 223.7 | +0.000 |
| q4：What is the smallest positive integer that can be written as the sum of two perfect squares, with both of these perfect squares being prime numbers? | 3 | 0→0→1 | 0→0→0 | 7.9 / 8.6 | -0.333 |
| q5：What is the title of the latest concert documentary film featuring Kendrick Lamar? | 3 | 0→0→0 | 0→1→1 | 11.2 / 9.6 | +0.667 |
| q6：What is the total number of branches of the Akhil Bharatiya Marathi Sahitya Mahamandal? | 1 | 0→缺→缺 | 0→缺→缺 | 137.6 / 130.7 | +0.000 |
| q7：Among this year's films that have grossed over $150 million worldwide, which has earned the least revenue? | 3 | 0→0→0 | 0→0→1 | 102.1 / 32.9 | +0.333 |
| q9：How many individuals have won the Oscar for Best Animated Feature? | 3 | 0→0→0 | 0→0→0 | 19.8 / 17.9 | +0.000 |
| q10：Which organization is the world's largest card payment processing organization, providing credit cards, debit cards, and electronic payment systems? | 3 | 0→0→0 | 0→0→0 | 16.4 / 16.4 | +0.000 |
| q11：According to Private Equity International's 2024 ranking, among all non-U.S.-based private equity firms with at least $30 billion raised over the past five years, which firm has the latest founding date? | 3 | 0→0→0 | 0→0→0 | 399.5 / 422.1 | +0.000 |
| q12：Which North Atlantic tropical storm, whose peak intensity remained at tropical storm level, caused the highest number of deaths last year? | 3 | 1→1→1 | 1→1→1 | 118.0 / 119.3 | +0.000 |
| q13：As of now, which country or countries have won a single medal in the history of the Summer Olympic Games—and it was a gold? | 3 | 1→0→0 | 1→1→1 | 47.1 / 76.5 | +0.667 |
| q14：As reported by the Food and Agriculture Organization of the United Nations, which nation ranked as the world’s second‑largest rice producer in 2023? | 3 | 0→0→1 | 1→0→1 | 11.3 / 13.8 | +0.333 |
| q15：How many YouTube videos have surpassed 5 billion views? | 3 | 1→1→1 | 1→1→1 | 18.6 / 11.3 | +0.000 |
| q16：According to United Nations data from 2021, what percentage of national parliamentary seats in Northern Africa were held by women? | 3 | 0→0→0 | 0→0→1 | 58.2 / 106.3 | +0.333 |
| q17：What is the current age of the youngest grandmaster of chess? | 3 | 1→1→1 | 1→1→1 | 37.3 / 47.0 | +0.000 |
| q18：What is the most recent film to join the top 10 highest-grossing films of all time? | 3 | 1→0→1 | 1→1→1 | 33.3 / 13.4 | +0.333 |
| q19：Who is the most recent female middle school student to represent China in the International Mathematical Olympiad (IMO) contest? | 3 | 1→0→0 | 1→0→0 | 238.3 / 102.6 | +0.000 |
| q20：How many versions of the .NET platform have been released that have a support lifetime of more than 12 months? | 3 | 0→0→0 | 0→0→0 | 17.6 / 19.3 | +0.000 |
| q21：Which tropical rainforest represents a quarter of the total area of remaining tropical forests on Earth and comprises one of the largest and most biodiverse tracts of tropical rainforest in the world? | 3 | 0→0→0 | 0→0→0 | 5.9 / 10.7 | +0.000 |
| q22：On what date did the KOSPI (Korea Composite Stock Price Index) experience its largest relative single-day drop? | 3 | 0→0→0 | 0→0→0 | 8.9 / 9.6 | +0.000 |
| q23：Among artists with multiple wins for Album of the Year at the Grammys, who has received the most nominations for this award, with each nomination occurring in a different year? | 3 | 0→0→1 | 0→0→0 | 367.0 / 563.6 | -0.333 |
| q24：How many active players are currently in the top 10 of all-time men’s international goal scorers in soccer? | 3 | 0→0→0 | 0→1→0 | 25.5 / 67.3 | +0.333 |
| q25：What is the smallest cube number which can be expressed as the sum of two different positive cube numbers in two different ways? | 3 | 1→0→0 | 1→0→0 | 2.3 / 3.3 | +0.000 |
| q26：According to United Nations data from 2015, what percentage of national parliamentary seats in Northern America were held by women? | 3 | 0→1→1 | 0→0→0 | 213.8 / 85.2 | -0.667 |
| q27：What percentage of the global mobile population is covered by 2G networks in 2024, according to the International Telecommunication Union (ITU)? | 3 | 1→0→0 | 0→0→0 | 11.3 / 144.2 | -0.333 |
| q28：How many Studio Ghibli feature films have received a Rotten Tomatoes Tomatometer score below 90%? | 3 | 0→0→0 | 0→0→0 | 39.4 / 71.9 | +0.000 |
| q30：Across all released seasons, how many episodes of The Lord of the Rings: The Rings of Power were not directed solely by Charlotte Brändström? | 3 | 1→1→0 | 1→1→1 | 111.0 / 44.3 | +0.333 |
| q31：What was Coco Gauff's WTA ranking points total immediately after last year's US Open – Women's Singles? | 3 | 1→1→1 | 1→1→1 | 13.1 / 29.3 | +0.000 |
| q32：How many of the heaviest living animals can reach a maximum mass exceeding 60 tonnes? | 3 | 1→0→0 | 1→0→0 | 172.6 / 25.6 | +0.000 |
| q33：Who was the purchaser in the largest confirmed merger or acquisition that ultimately failed to complete? | 3 | 0→1→1 | 0→0→0 | 15.1 / 28.9 | -0.667 |
| q34：Which American airline has most recently filed for Chapter 7 bankruptcy protection? | 3 | 1→1→0 | 1→1→1 | 12.9 / 17.5 | +0.333 |
| q35：How many of the top 50 most-followed Instagram accounts belong to individuals or entities based in the United States? | 3 | 1→1→1 | 0→1→1 | 53.9 / 134.4 | -0.333 |
| q37：How many American artists have received more than 40 Grammy nominations? | 3 | 0→0→0 | 0→0→0 | 16.4 / 26.0 | +0.000 |
| q38：Which two countries share the longest continuous international border in the world by total length? | 2 | 0→0→缺 | 0→0→缺 | 2.3 / 10.0 | +0.000 |
| q39：Who is currently the most highly decorated IOI contestant with 5 golds and 1 bronze medal? | 3 | 1→1→1 | 0→1→1 | 119.7 / 61.9 | -0.333 |
| q41：Which three North American countries will host the 2026 FIFA's Women World Cup, the first to be co-hosted by three nations and the first North American World Cup since 1994? | 3 | 1→1→1 | 1→1→1 | 14.1 / 15.1 | +0.000 |
| q42：How many films released before 2020 are currently among the top 30 highest-grossing films worldwide? | 3 | 0→0→0 | 0→0→0 | 13.9 / 16.5 | +0.000 |
| q43：What was the acceptance rate for the most recent Conference on Empirical Methods in Natural Language Processing (EMNLP), including both the main conference and Findings? | 3 | 1→1→1 | 1→1→1 | 32.2 / 11.2 | +0.000 |
| q44：What is the total number of documentary films produced by Sahitya Akademi? | 3 | 0→0→0 | 0→0→0 | 13.0 / 18.9 | +0.000 |
| q47：What is the valency of mercury in Mercury(I) chloride? | 3 | 0→0→0 | 0→0→0 | 6.9 / 1.8 | +0.000 |
| q48：Who broke the short course world record in women's 400m freestyle at the youngest age from 2010 to now? | 3 | 1→1→1 | 1→1→0 | 956.5 / 510.0 | -0.333 |
| q49：What is the name of the largest wildfire in Northern California last year? | 3 | 0→0→0 | 0→0→0 | 11.7 / 25.8 | +0.000 |
| q51：Who was the last Bayern Munich player to finish in the top three for the Ballon d'Or? | 3 | 0→0→0 | 0→0→0 | 13.3 / 41.0 | +0.000 |
| q52：How many individuals from the Liberal Democratic Party have served as Prime Minister of Japan since the assassination of Shinzo Abe? | 3 | 0→0→0 | 0→0→0 | 14.5 / 28.2 | +0.000 |
| q53：According to the WHO, in which year were the highest number of measles cases recorded worldwide? | 3 | 0→0→0 | 0→0→0 | 19.4 / 11.2 | +0.000 |
| q54：How many of the top 30 most-liked YouTube videos belong to MrBeast? | 3 | 1→1→1 | 0→0→0 | 54.4 / 17.3 | -1.000 |
| q55：For exactly how many days did the Instagram post by Justin Bieber's account that once held the record for most-liked post on the platform remain at the top? | 2 | 0→1→缺 | 0→0→缺 | 58.5 / 219.2 | -0.500 |
| q56：How many players have officially worn the No. 10 shirt for Barcelona's men's first team since Diego Maradona left the club in 1984? | 3 | 0→0→0 | 0→0→0 | 21.8 / 104.2 | +0.000 |
| q57：How many airlines are members of IATA, the organization that supports airline activity and helps formulate industry policy and standards? | 3 | 0→0→0 | 0→0→0 | 9.1 / 3.9 | +0.000 |
| q59：How many times in history has the PDC World Darts Championship final featured two English players? | 3 | 1→1→1 | 1→1→1 | 77.1 / 15.5 | +0.000 |
| q60：Of the drivers who have won consecutive World Drivers' Championships, how many competed in this year's Championship? | 3 | 0→0→0 | 0→0→0 | 103.6 / 107.0 | +0.000 |
| q61：In what year did the deadliest Philippine typhoon of the first decade of the 21st century occur? | 3 | 1→1→1 | 1→1→1 | 11.4 / 11.9 | +0.000 |
| q62：How many videos on YouTube have received more than 29 million likes? | 2 | 0→0→缺 | 1→1→缺 | 30.0 / 37.8 | +1.000 |
| q63：How many Los Angeles Metro Rail stations are served by both the A Line and at least one other Metro Rail line? | 3 | 1→1→0 | 1→1→0 | 16.1 / 16.5 | +0.000 |
| q65：Who holds the all-time record at the Grammys for the most wins in the album of the year category? | 3 | 0→1→1 | 1→1→0 | 13.6 / 14.8 | +0.000 |
| q66：On what date did the latest eruption of the world's most active composite volcano begin, which spewed fiery lava and ash thousands of feet into the sky? | 3 | 0→0→0 | 0→0→0 | 177.7 / 276.5 | +0.000 |
| q68：How many NBA players have scored 60 or more points in a regular season game since 2023? | 3 | 0→1→1 | 1→0→0 | 66.7 / 42.5 | -0.333 |
| q69：How many of the top 10 highest-paid athletes in the latest Forbes list are professional golfers living in the U.S.? | 3 | 0→0→0 | 0→0→1 | 51.3 / 23.5 | +0.333 |
| q70：How many badminton athletes have won Olympic Gold and more than 2 Olympic medals in total? | 3 | 0→1→0 | 0→0→0 | 38.6 / 46.2 | -0.333 |
| q71：According to Vietcombank's exchange rate table on May 1, 2025, what was the cash buying rate for the US dollar (USD)? | 3 | 0→1→1 | 1→1→0 | 47.6 / 83.5 | +0.000 |
| q72：According to 2023 data from the U.S. Environmental Protection Agency, which sector produced the lowest CO₂ emissions in the state of Indiana? | 3 | 0→0→0 | 0→0→0 | 27.8 / 33.0 | +0.000 |
| q73：How many former US presidents ran again for president after losing a general election and lost on their second attempt? | 3 | 0→1→0 | 0→0→0 | 57.0 / 54.4 | -0.333 |
| q74：Which non-American agency has the most followers on X? | 3 | 1→0→1 | 0→0→1 | 109.5 / 174.9 | -0.333 |
| q75：How many non-brand TikTok accounts have reached more than 50 million followers? | 3 | 0→0→0 | 0→0→0 | 25.9 / 18.5 | +0.000 |
| q76：What is the sum of all three-letter Roman numerals that read the same forwards and backwards? | 3 | 1→1→1 | 1→1→1 | 9.9 / 11.1 | +0.000 |
| q78：How many Super Bowl games had an attendance of more than 70,000? | 3 | 0→0→0 | 0→1→0 | 25.6 / 36.3 | +0.333 |
| q79：How many Studio Ghibli feature films have been released with a runtime of 119 minutes or longer? | 3 | 1→0→1 | 1→0→0 | 23.3 / 14.7 | -0.333 |
| q80：In what month and year was the water level of Lake Powell last below 3550 feet? | 3 | 0→0→0 | 0→0→0 | 14.0 / 15.0 | +0.000 |
| q81：What was the average 911 call answer time in Washington D.C. on April 30, 2025? | 3 | 0→0→0 | 0→1→0 | 135.4 / 136.6 | +0.333 |
| q82：At which awards ceremony did the film Oppenheimer, a solemn three-hour biopic that became an unlikely billion-dollar box-office sensation, first win the Best Film award? | 3 | 0→0→0 | 0→0→0 | 17.9 / 13.2 | +0.000 |
| q83：How many YouTube music videos have surpassed 7 billion views? | 3 | 0→0→0 | 0→0→0 | 10.1 / 10.3 | +0.000 |
| q84：Who was the most recent Sheriff of Los Angeles County killed in the line of duty? | 3 | 0→0→0 | 0→0→0 | 27.6 / 35.6 | +0.000 |
| q85：What is the name of the in-place, stable comparison sorting algorithm with a worst-case time complexity of O(n log n) and a best-case time complexity of O(n)? | 3 | 0→0→1 | 0→0→0 | 17.0 / 8.5 | -0.333 |
| q86：How many of the 50 most-subscribed YouTube channels use only English as their primary language? | 3 | 0→0→0 | 0→0→0 | 169.1 / 139.0 | +0.000 |
| q87：Which is the most recent film to dominate the British Academy Film Awards by winning more than seven awards while also having the most total wins and nominations in its award year? | 2 | 0→缺→0 | 1→缺→0 | 172.7 / 446.8 | +0.500 |
| q88：If I randomly select i.i.d. samples from a distribution n times, the distribution of the sampled variables will approximately follow a normal distribution as n becomes very large. This statement is based on which theory? | 3 | 0→0→0 | 0→0→0 | 9.6 / 1.7 | +0.000 |
| q89：Among women’s soccer players with 100 or more international goals, who has the highest goals-per-match ratio? | 3 | 1→1→1 | 1→1→1 | 154.1 / 166.2 | +0.000 |
| q90：How many state-level felonies has the most recent former president of the United States been convicted of? | 3 | 1→1→0 | 1→1→0 | 71.9 / 23.0 | +0.000 |
| q91：How many of the top 20 most-liked Instagram posts by non-football-related accounts—excluding footballers like Lionel Messi and Cristiano Ronaldo and football organizations—also appear in the overall top 20 most-liked posts? Note that Selena Gomez does not have any posts in the overall top 20 most-liked posts. | 3 | 0→0→0 | 0→0→0 | 325.5 / 179.4 | +0.000 |
| q92：For exactly how many days did the Instagram post by Kendall Jenner's account that once held the record for most-liked post on the platform remain at the top? | 2 | 0→缺→0 | 0→缺→0 | 294.9 / 207.6 | +0.000 |
| q93：Who is the only female artist to have topped Spotify's list of most-streamed artists in three consecutive years (2020–2022)? | 3 | 1→0→0 | 1→0→1 | 27.8 / 22.5 | +0.333 |
| q94：How many of the top 50 most-subscribed YouTube channels are based in India? | 3 | 1→1→1 | 1→0→1 | 24.0 / 86.0 | -0.333 |
| q95：I am a father of two undergraduate sons enrolling in Virginia Tech's Virtual Campus for Summer 2025. One is a Virginia resident taking 6 credit hours, and the other is a non-resident taking 8 credit hours. What is the total tuition I need to pay for both? | 3 | 1→0→1 | 1→1→1 | 869.4 / 390.3 | +0.333 |
| q96：Google is significantly expanding its presence in the Asia-Pacific region, with Singapore as their current Asia Pacific headquarters. How many office locations does the company currently operate across Asian countries? | 1 | 0→缺→缺 | 0→缺→缺 | 33.8 / 19.1 | +0.000 |
| q98：How many countries were not listed as offering only paid access to YouTube Music at the time of its initial expansion in 2018? | 3 | 0→0→0 | 1→0→0 | 50.9 / 26.4 | +0.333 |
| q100：How many countries did both Donald Trump (during his first term) and Joe Biden visit during their presidencies, including the West Bank? | 2 | 0→0→缺 | 0→1→缺 | 149.9 / 77.8 | +0.500 |
| q102：According to the ICT Development Index (IDI) 2024, how many countries scored below 25? | 3 | 1→1→1 | 0→0→1 | 104.0 / 307.1 | -0.667 |
| q103：How many hotels in the United States have more than 3,500 rooms? | 3 | 1→0→0 | 0→1→1 | 106.3 / 44.3 | +0.333 |
| q106：How many books has Jamie Oliver published since 2020? | 3 | 0→0→0 | 0→0→0 | 10.0 / 10.4 | +0.000 |
| q107：According to the U.S. Census Bureau 2022 data, how many states had more than 25% of their population aged 25 and older holding an advanced degree? | 3 | 0→1→0 | 0→1→0 | 468.4 / 326.5 | +0.000 |
| q108：How many times has the Turing Award been given to multiple winners in the same year? | 3 | 1→1→1 | 1→1→1 | 23.4 / 16.2 | +0.000 |
| q109：How many smoke grenade models listed in the Polish Land Forces equipment originate exclusively from the Soviet Union? | 3 | 1→0→1 | 1→1→1 | 38.6 / 107.5 | +0.333 |
| q110：How many movies with an estimated net budget of $350 million or more were not the highest-grossing film of their release year? | 3 | 0→1→1 | 1→0→0 | 210.5 / 433.5 | -0.333 |
