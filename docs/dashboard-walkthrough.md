# Dashboard walkthrough

Follow the [README setup](../README.md#run-locally) and start the application. The screenshots use synthetic demonstration records, including an E-901 example article that is not bundled. Source counts and references can differ in your installation. Live AI drafting requires your own confirmed-free provider key.

## 1. Choose a workspace

![Support Agent and Knowledge Editor choices](assets/dashboard/01-workspaces.png)

Choose **Support Agent** to handle a complaint or **Knowledge Editor** to manage evidence and reviews. Editor access requires the configured application key; role selection alone grants no permissions. Light/Dark changes appearance only.

## 2. Describe the complaint

![Complaint entry](assets/dashboard/02-complaint.png)

Enter the complaint. Device and additional details are optional. Select only fixes actually tried, and describe their results when known. **Load an example** fills the form without submitting it.

**Prepare troubleshooting draft** classifies the complaint, searches evidence and checks selected steps. **Search supporting sources** retrieves evidence without preparing a draft. Neither action saves a case automatically. Avoid unnecessary personal data; supported identifiers are masked, but masking is limited.

## 3. Review the suggested resolution

![Cited draft and already-tried action](assets/dashboard/03-cited-draft.png)

Check the **Already tried** banner and proposed steps. Recognized attempts are excluded before step selection. Each step cites its source and version. Review applicability before using a suggested action.

## 4. Inspect supporting evidence

![Supporting quote and applicability](assets/dashboard/04-step-evidence.png)

Expand a step to read its source quote, conditions and matching customer information. **Cited sources** contains the complete records. Knowledge articles and resolved history are preferred; public suggestions remain labelled unverified.

## 5. Answer clarification questions

![Answer fields beneath clarification questions](assets/dashboard/13-clarification.png)

Enter an answer beneath each question and select **Continue**. The original complaint and answers are submitted together as current-case context. Leave unknown answers blank or say you are unsure. There is no chatbot memory.

## 6. Save a case and record the outcome

![Pending saved case](assets/dashboard/05-pending-case.png)

Choose **Save case for follow-up**, then open it in **Saved Cases**. Record actions actually performed, whether the problem was resolved and what confirms the outcome. Leave it pending until an outcome is reported or observed. Saving a suggestion does not make it searchable history.

## 7. Review and publish history

![Editor review](assets/dashboard/06-editor-review.png)

An editor checks the actual actions, reported outcome, product/category and applicability. Supply a rationale, confirm the review, then approve publication or reject the case.

![Published historical source](assets/dashboard/07-published-case.png)

After the background job succeeds, the case shows its source reference and version. Resolved outcomes become resolved history; unsuccessful outcomes retain unresolved labels. This workflow records human reports rather than automatically proving success.

## 8. Search articles and published cases

![Evidence Explorer results](assets/dashboard/08-evidence-search.png)

Use **Evidence Explorer** to search matching words, similar meaning or both. Product/type filters narrow results. Approved history appears alongside existing evidence.

**Relevance rank: N of M** describes position among returned results. Numeric scores are under **Match details**; they are not percentages of correctness. **Open a source by ID** is a direct lookup: enter a reference such as `KB-003`, with version 0 for the latest or a specific cited version.

## 9. Maintain evidence

![Evidence publishing form](assets/dashboard/09-evidence-form.png)

Use **Add**, **Update** or **Retire** with source origin, action instructions and applicability conditions. Check the job status after submitting. Retirement removes a source from current search but preserves cited versions. Advanced batch import is optional for multi-record JSON updates.

## 10. Review emerging topics

![Emerging-topic proposals](assets/dashboard/10-emerging-topics.png)

Review recurring weak-match complaints and proposed categories. Approve a category or dismiss the proposal with a rationale. Category approval does not create a fix or retrain the model. The screenshot's satellite examples demonstrate the grouping workflow.

## 11. Check system health

![Service health](assets/dashboard/11-system-health.png)

Inspect service availability, searchable evidence, semantic readiness, response times and errors. AI configuration does not confirm provider availability. Fallback counts describe past requests; counters reset on restart. Health measurements are separate from [evaluation scores](evaluation.md).

![Health in dark appearance](assets/dashboard/12-dark-health.png)

Optional technical details provide diagnostics. Changing appearance does not change data or functionality.
