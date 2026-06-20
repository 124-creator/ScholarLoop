# M020 B-lite evidence matrix report

- Status: **PASS**
- Query docs rendered: 30
- Top-N per query: 3
- fabrication_rate: `0.0`
- official missing-field compliance: `1.0`

## Status distribution

- 存在争议: 46
- 已有证据支持: 673
- 证据不足: 1
- 需人工核验: 180

## Demonstration examples

### litsearch_000

Query: Are there any research papers on methods to compress large-scale language models using task-agnostic knowledge distillation techniques?

| rank | corpusid | title | large language model compression methods | knowledge distillation for language models | task-agnostic knowledge distillation |
|---:|---:|---|---|---|---|
| 1 | 221995575 | Contrastive Distillation on Intermediate Representations for Language Model Comp | ✅ Existing language model compression methods mostly use a simple L 2 loss to distill knowledge in the intermediate repres | ✅ Existing language model compression methods mostly use a simple L 2 loss to distill knowledge in the intermediate repres | ✅ Existing language model compression methods mostly use a simple L 2 loss to distill knowledge in the intermediate repres |
| 2 | 258212842 | An Empirical Study of Leveraging Knowledge Distillation for Compressing Multilin | ✅ Although existing literature mainly discusses bilingual-to-multilingual or bilingual-to-bilingual distillation, to the b | ✅ Knowledge distillation (KD) is a wellknown method for compressing neural models. | ✅ Knowledge distillation (KD) is a wellknown method for compressing neural models. |
| 3 | 218502458 | XtremeDistil: Multi-stage Distillation for Massive Multilingual Models | ✅ We show that our approach leads to massive compression of teacher models like mBERT by upto 35x in terms of parameters a | ✅ Some recent works use knowledge distillation to compress these huge models into shallow ones. | ✅ Some recent works use knowledge distillation to compress these huge models into shallow ones. |

#### First card fields
- **title** [已有证据支持]: Contrastive Distillation on Intermediate Representations for Language Model Compression
- **authors_year** [需人工核验]: online_connector_required_for_author_year_source_doi
- **source_or_doi** [需人工核验]: online_connector_required_for_author_year_source_doi
- **recommendation_reason** [已有证据支持]: achieves superb performance on the GLUE benchmark, outperforming state-of-the-art compression methods.
- **supported_research_question** [已有证据支持]: Existing language model compression methods mostly use a simple L 2 loss to distill knowledge in the intermediate representations of a large
- **method** [已有证据支持]: we propose Contrastive Distillation on Intermediate Representations (CODIR), a principled knowledge distillation framework where the student
- **data_or_scenario** [已有证据支持]: CoDIR can be readily applied to compress large-scale language models in both pretraining and finetuning stages, and achieves superb performa
- **main_conclusion** [已有证据支持]: outperforming state-of-the-art compression methods.
- **limitations** [存在争议]: Although widely used, this objective by design assumes that all the dimensions of hidden representations are independent, failing to capture
- **relevance_strength** [已有证据支持]: achieves superb performance on the GLUE benchmark, outperforming state-of-the-art compression methods.

### litsearch_001

Query: Are there any resources available for translating Tunisian Arabic dialect that contain both manually translated comments by native speakers and additional data augmented through methods like segmentation at stop words level?

| rank | corpusid | title | Tunisian Arabic translation dataset native speaker comments | data augmentation segmentation stop words Arabic dialect translation | Tunisian Arabic dialect parallel corpus augmented translation |
|---:|---:|---|---|---|---|
| 1 | 252432736 | Standardization of Dialect Comments in Social Networks in View of Sentiment Anal | ✅ With the growing access to the internet, the spoken Arabic dialect language becomes an informal languages written in soc | ✅ With the growing access to the internet, the spoken Arabic dialect language becomes an informal languages written in soc | ✅ With the growing access to the internet, the spoken Arabic dialect language becomes an informal languages written in soc |
| 2 | 6825507 | Sentiment Analysis of Tunisian Dialect: Linguistic Resources and Experiments | ✅ Dialectal Arabic (DA) is significantly different from the Arabic language taught in schools and used in written communic | ✅ Dialectal Arabic (DA) is significantly different from the Arabic language taught in schools and used in written communic | ✅ Dialectal Arabic (DA) is significantly different from the Arabic language taught in schools and used in written communic |
| 3 | 227231792 | Parallel resources for Tunisian Arabic dialect translation | ✅ The difficulty of processing dialects is clearly observed in the high cost of building representative corpus, in particu | ✅ The difficulty of processing dialects is clearly observed in the high cost of building representative corpus, in particu | ✅ The difficulty of processing dialects is clearly observed in the high cost of building representative corpus, in particu |

#### First card fields
- **title** [已有证据支持]: Standardization of Dialect Comments in Social Networks in View of Sentiment Analysis : Case of Tunisian Dialect
- **authors_year** [需人工核验]: online_connector_required_for_author_year_source_doi
- **source_or_doi** [需人工核验]: online_connector_required_for_author_year_source_doi
- **recommendation_reason** [已有证据支持]: With the growing access to the internet, the spoken Arabic dialect language becomes an informal languages written in social media.
- **supported_research_question** [已有证据支持]: With the growing access to the internet, the spoken Arabic dialect language becomes an informal languages written in social media.
- **method** [已有证据支持]: This linguistic situation inhibits mutual understanding between internet users and makes difficult to use computational approaches since mos
- **data_or_scenario** [已有证据支持]: Each of these steps was evaluated on the same test corpus.
- **main_conclusion** [已有证据支持]: Then, the resulting comments are translated using a neural translation model.
- **limitations** [存在争议]: In effect, MSA presents the formal language for all Arabic dialects, but they are different at all linguistic levels.
- **relevance_strength** [已有证据支持]: With the growing access to the internet, the spoken Arabic dialect language becomes an informal languages written in social media.

### litsearch_002

Query: Are there any studies that explore post-hoc techniques for hallucination detection at both the token- and sentence-level in neural sequence generation tasks?

| rank | corpusid | title | post-hoc hallucination detection token-level neural generation | sentence-level hallucination detection post-hoc neural generation | post-hoc techniques hallucination detection token sentence level |
|---:|---:|---|---|---|---|
| 1 | 226254579 | Detecting Hallucinated Content in Conditional Neural Sequence Generation | ✅ Neural sequence models can generate highly fluent sentences, but recent studies have also shown that they are also prone | ✅ Neural sequence models can generate highly fluent sentences, but recent studies have also shown that they are also prone | ✅ Neural sequence models can generate highly fluent sentences, but recent studies have also shown that they are also prone |
| 2 | 233296648 | A Token-level Reference-free Hallucination Detection Benchmark for Free-form Tex | ✅ Existing work usually attempts to detect these hallucinations based on a corresponding oracle reference at a sentence or | ✅ Existing work usually attempts to detect these hallucinations based on a corresponding oracle reference at a sentence or | ✅ Existing work usually attempts to detect these hallucinations based on a corresponding oracle reference at a sentence or |
| 3 | 256000114 | Understanding and Detecting Hallucinations in Neural Machine Translation via Mod | ✅ Neural sequence generation models are known to ''hallucinate'', by producing outputs that are unrelated to the source te | ✅ Neural sequence generation models are known to ''hallucinate'', by producing outputs that are unrelated to the source te | ✅ These hallucinations are potentially harmful, yet it remains unclear in what conditions they arise and how to mitigate t |

#### First card fields
- **title** [已有证据支持]: Detecting Hallucinated Content in Conditional Neural Sequence Generation
- **authors_year** [需人工核验]: online_connector_required_for_author_year_source_doi
- **source_or_doi** [需人工核验]: online_connector_required_for_author_year_source_doi
- **recommendation_reason** [已有证据支持]: Neural sequence models can generate highly fluent sentences, but recent studies have also shown that they are also prone to hallucinate addi
- **supported_research_question** [已有证据支持]: we propose a task to predict whether each token in the output sequence is hallucinated (not contained in the input)
- **method** [已有证据支持]: a method for learning to detect hallucinations using pretrained language models fine tuned on synthetic data that includes automatically ins
- **data_or_scenario** [已有证据支持]: Experiments on machine translation (MT) and abstractive summarization demonstrate that our proposed approach consistently outperforms strong
- **main_conclusion** [已有证据支持]: our proposed approach consistently outperforms strong baselines on all benchmark datasets.
- **limitations** [存在争议]: Neural sequence models can generate highly fluent sentences, but recent studies have also shown that they are also prone to hallucinate addi
- **relevance_strength** [已有证据支持]: predict whether each token in the output sequence is hallucinated
