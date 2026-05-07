# CLAUDE.md
# **LegiLens: Colorado Project Overview**

## **1\. Project Mission**

To quantify the "Friction Gap" in the Colorado General Assembly by analyzing the discrepancy between legislative rhetoric and administrative/technical reality. LegiLens provides an objective, data-driven lens to evaluate how every bill aligns with technical logic, administrative efficiency, and the "Common Good" (The We-The-People Metric).

## **2\. Core Analysis Modules (Universal Framework)**

### **A. The Signal-to-Noise Processor (SNP)**

* **Method:** Uses NLP to compare the "Bill Vocabulary" (actual text and definitions) against the "Transcript Vocabulary" of speakers.  
* **Metric:** **Topic Adherence Score**. Detects when floor or committee time is diverted for campaign-style grandstanding or non-germane topics, measuring the literal time-cost of performative politics.

### **B. The Administrative Logic Engine (ALE)**

* **Method:** A RAG (Retrieval-Augmented Generation) system holding "Reality Baselines" (Colorado Revised Statutes, agency SOPs, and technical standards like POSIX/NIST).  
* **Metric:** **Reality Mismatch Flag**. Triggered when a legislator makes a claim that contradicts physics, geography, established administrative protocol, or technical architecture.

### **C. The Common Good Evaluator (CGE)**

* **Method:** Analyzes the distribution of a bill's financial and social impact across the general population.  
* **Metric:** **Utility Weighting**.  
  * **Fee-Shifting Detection:** Identifies bills that use flat fees (regressive) to avoid the political friction of graduated taxes (progressive).  
  * **Extraction Analysis:** Highlights tax credits or carve-outs that benefit narrow special interests while depleting the General Fund for schools and public infrastructure.

### **D. The Influence & Source Tracker (IST) \- NEW**

* **Method:** Uses **Text Reuse Detection** (min-hashing or Smith-Waterman algorithms) to compare Colorado bill text against a national database of 50-state legislation and known "Model Bills."  
* **Metric:** **Source Authenticity Score**.  
  * **"Copycat" Alert:** Triggered when a bill shares \>70% identical language with bills introduced in other states or model templates.  
  * **Dark Money Correlation:** Cross-references "Copycat" bills with campaign contribution data to identify high-probability "pay-to-play" legislation.

## **3\. Universal Friction & Fairness Tags**

| Tag | Definition | Global Application |
| :---- | :---- | :---- |
| **Technical Conflict** | Mandates that break existing technical standards or architecture. | Any bill regulating software, encryption, or digital platforms. |
| **Spatial Inconsistency** | Proposals that are geographically or logistically impossible. | Land use, buffer zones, or infrastructure mandates. |
| **Expert Defiance** | Disregarding non-partisan expert testimony for "intuitive" logic. | Ignoring ALJs, agency heads, or scientists during hearings. |
| **Regressive Burden** | Using flat fees to fund public goods, impacting the majority. | New "enterprise" fees or delivery surcharges. |
| **Source-Cloned** | Identical to model legislation or bills in 5+ other states. | Indicates imported special-interest agendas over local needs. |
| **Legal Hallucination** | Citing inapplicable legal theories to create delay or obstruction. | Frivolous constitutional or contract law claims. |

## **4\. Visualizations**

* **The "Taxpayer Burden" Shift:** A longitudinal chart showing the growth of fees vs. taxes, illustrating the "hidden" cost of political expediency.  
* **The "Expert-to-Amateur" Ratio:** Compares time given to verified experts versus time taken by representatives to rebut them with non-factual anecdotes.  
* **The "Influence Map":** A visual network showing how identical language travels from national think tanks into the Colorado House floor.

Always invoke the using-superpowers skill at the start of a session.