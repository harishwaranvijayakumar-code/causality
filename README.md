
## Trace input sources

Causality accepts a baseline dataset and a degraded dataset from three sources:

- **Paste JSON:** Enter a dataset in Causality's trace JSON format.
- **Upload JSON:** Upload a `.json` file for either dataset.
- **Jaeger:** Retrieve traces from a configured Jaeger Query service.

Each dataset is limited to 1 MiB. Successful comparisons save the normalized input datasets and analysis results using the existing database persistence workflow.

### Jaeger configuration

Set `JAEGER_QUERY_URL` to the base URL of the Jaeger Query service.

Local example:

```dotenv
JAEGER_QUERY_URL=http://localhost:16686
```

The Django backend must be able to reach this address. When hosted, configure `JAEGER_QUERY_URL` in the hosting provider's environment settings. Do not assume `localhost` refers to the developer's computer when Causality is deployed.

In the comparison form, select **Query Jaeger** for a dataset, then enter its service name, start time, end time, and trace limit. The permitted limit is 1 to 100 traces.

The configured Jaeger endpoint must be reachable and compatible with the Jaeger Query API. An empty result, invalid response, timeout, or connection error is reported as an input error.

### Trace data privacy

Successful comparisons store the input datasets and results in the configured database. Remove credentials, personal information, and other confidential attributes before ingestion. Configure access to Jaeger and the database according to your deployment's security requirements.

### Input limits

- JSON dataset: maximum 1 MiB each.
- Jaeger response: maximum 8 MiB.
- Jaeger query: maximum 100 traces.
- Jaeger request timeout: 8 seconds.
- Multipart request body: maximum 3 MiB.
