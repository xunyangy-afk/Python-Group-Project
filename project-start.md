# Financial Agent Deployment

## Why our team is interested in it

Because it explores the extent to which AI agents can be trusted in real-world business decision-making. By putting ourselves in the shoes of actual decision-makers, we can examine which model should handle which task, when human review is necessary, when an agent run should be stopped, and whether the added performance of a more expensive model justifies the additional cost. We believe questions around AI adoptability, governance, and workflow design have significant potential in the financial industry and could also be extended to many other industries in the near future.

## Vision A

A Director of Internal Audit Analytics at Citi must decide which AI-generated XBRL verification results can be automatically cleared and which must be escalated to deterministic or human review.

## Vision B

A Head of Equity Research Operations at BlackRock must decide which agent–model configuration should be the default system for generating weekly equity-research reports while meeting a minimum quality standard at acceptable cost and latency.

## Core Data Access

TheFinAI/Herculean dataset on Hugging Face Link:  
https://huggingface.co/datasets/TheFinAI/Herculean

We successfully accessed the dataset page and Dataset Viewer on Hugging Face. The dataset provides financial data for eight large U.S. technology companies, including daily stock prices, news highlights, and excerpts from 10-K and 10-Q SEC filings. The core data are available in Parquet format and as a DuckDB database, so they can be accessed and analyzed with Python.

## Three Questions

1. How much API budget will we actually need to generate the cost, latency and score data ourselves?  
   *(We don't know how many task samples or which models we will need to run, what that would cost, or how we will fund it.)*

2. How trustworthy is Herculean's report evaluation for Vision B?  
   *(Our team is curious about the validity of the dataset.)*

3. Is it okay to use a fictional/generic company name (ex. a large asset manager) for the company, or do you want us to research and use a real firm's actual practices?
