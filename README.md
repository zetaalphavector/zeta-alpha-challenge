# ZAV-challenge

At zeta-alpha we’re building the [next generation neural discovery platform](https://search.zeta-alpha.com). Our platform allows you to find documents, stay up-to-date on relevant developments, and organize your knowledge discovery work. Our search system is the part that ingests, understands, and retrieves documents from multiple sources.

## Assignment 1: Design a search system

The main objective of this challenge is for you to design a version of our search system that includes:
- An offline stage that periodically polls multiple data sources (external APIs, websites, etc.), processes them, and populates a search database.
- A retrieval system that allows users to search, rank, and sort the documents from the database.

### Requirements
Your design should satisfy the following requirements:

1. Allow data and content managers to easily manage data sources, as well as individual documents within the sources. 
1. Allow NLP/ML engineers to easily experiment and develop processing workflows.
1. Allow search engineers to tweak and develop the retrieval process.
1. Allow end-users to interact with the platform in a fast, reliable, and secure way.

### Deliverables

Create a design document showing how the different parts of the system are connected and how the data flows between them. Explain how your design satisfies the aforementioned requirements.

## Assignment 2: Implement a search system MVP

In this part of the challenge you are required to create an MVP of the search system. You are provided with a source folder containing multiple PDF documents. Your objective is to implement a solution capable of:
1. Ingesting, parsing, and storing the provided documents
1. Retrieving a list of documents by matching the title, authors, and/or content.

**You can find the source documents [here](link-to-s3).**

### Deliverables

The result should be in the form of functional code along with documentation for running and using it. Also state what could be the next steps in order to satisfy the requirements of the design assignment.

## Tips and remarks

- You should not spend more than 8 hours working on the challenge.
- The coding assignment should be written in **python**.
- You can choose any existing libraries and packages that you deem necessary.
- Expect to be questioned about your technology and architectural decisions, as well as implementation details.
- Work in an agile way. You might not be able to completely solve all the assignments, so pick wisely.
- Don't hesitate to contact us with any clarification questions.