### Query Roboflow Inference Predictions from Supabase with Python

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/ai/integrations/roboflow.mdx

This Python snippet shows how to retrieve previously saved inference predictions from a Supabase table. It queries the 'predictions' table, filtering results by the 'filename' column, and prints the fetched data.

```python
result = supabase.table('predictions') \
    .select("predictions") \
    .filter("filename", "eq", image) \
    .execute()

print(result)
```

--------------------------------

### Fetch and Display All Posts Statically with Next.js Server Component (Initial)

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-11-17-fetching-and-caching-supabase-data-in-next-js-server-components.mdx

This Next.js Server Component fetches all posts from a Supabase table and displays them as a JSON string. It leverages `async/await` directly in the component, allowing Next.js to handle data fetching and suspend rendering until data is ready, keeping the rendering logic clean.

```jsx
import supabase from '../../utils/supabase'

export default async function Posts() {
  const { data: posts } = await supabase.from('posts').select()
  return <pre>{JSON.stringify(posts, null, 2)}</pre>
}
```

--------------------------------

### Fetch Data Server-Side

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/getting-started/quickstarts/sveltekit.mdx

Implement server-side data fetching using SvelteKit's load function to query Supabase database and return instruments data.

```javascript
import { supabase } from "$lib/supabaseClient";

export async function load() {
  const { data } = await supabase.from("instruments").select();
  return {
    instruments: data ?? [],
  };
}
```

```typescript
import type { PageServerLoad } from './$types';
import { supabase } from '$lib/supabaseClient';

type Instrument = {
  id: number;
  name: string;
};

export const load: PageServerLoad = async () => {
  const { data, error } = await supabase.from('instruments').select<'instruments', Instrument>();

  if (error) {
    console.error('Error loading instruments:', error.message);
    return { instruments: [] };
  }

  return {
    instruments: data ?? [],
  };
};
```

--------------------------------

### Pass cookie header with fetch request for session access

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/troubleshooting/fetch-requests-to-api-endpoints-arent-showing-the-session-UbUwRs.mdx

This TypeScript snippet demonstrates how to include the cookie header when making fetch requests to API endpoints. The cookie must be explicitly passed from the incoming request headers to maintain session information. This is necessary because fetch requests do not automatically include cookies by default.

```typescript
const res = await fetch('http://localhost:3000/contact', {
  headers: {
    cookie: headers().get('cookie') as string,
  },
})
```

--------------------------------

### Fetch Slack Channels from Supabase in Python

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-08-09-slack-consolidate-slackbot-to-consolidate-messages.mdx

The `setup` function retrieves a list of configured Slack channels from the 'slack_channels' table in Supabase. It processes the fetched data to create a dictionary of `SlackChannel` objects, indexed by their channel IDs.

```python
def setup():
    """_summary_
        Fetches the list of channels from Supabase and returns them in a dict()
    Returns:
        dict: Dictionary with SlackChannel objects.
    """
    channels = dict()
    data = supabase.from_("slack_channels").select("channel_id, channel, p_level, dest_channel, dest_channel_id, private").execute().data
    data_dic = data
    for row in data_dic:
        channels[row['channel_id']] = SlackChannel(id = row['channel_id'],
        name = row['channel'],
        p_level = row['p_level'],
        dest_channel = row['dest_channel'],
        dest_channel_id = row['dest_channel_id'],
        private = row['private'])
    return channels
```

--------------------------------

### Fetch and Display Posts Dynamically on Every Request (Next.js TypeScript)

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-11-17-fetching-and-caching-supabase-data-in-next-js-server-components.mdx

This Next.js component fetches and displays a list of posts from Supabase, similar to a server-side rendered page. By setting `revalidate = 0`, the component ensures that data is fetched on every incoming request, providing the freshest possible data at the cost of potential increased server load compared to static revalidation.

```tsx
import Link from 'next/link'
import supabase from '../../utils/supabase'

export const revalidate = 0

export default async function Posts() {
  const { data: posts } = await supabase.from('posts').select('id, title')

  if (!posts) {
    return <p>No posts found.</p>
  }

  return posts.map((post) => (
    <p key={post.id}>
      <Link href={`/static/${post.id}`}>{post.title}</Link>
    </p>
  ))
}
```

--------------------------------

### Fetch Supabase Data Client-Side in Next.js Client Component

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-11-17-fetching-and-caching-supabase-data-in-next-js-server-components.mdx

This Next.js Client Component demonstrates fetching data from Supabase client-side. It utilizes the 'use client' directive, `useEffect` to perform an asynchronous data fetch from the 'posts' table on component mount, and `useState` to manage loading state and display the fetched data.

```tsx
'use client'

import { useEffect, useState } from 'react'
import supabase from '../../utils/supabase'

export default function ClientPosts() {
  const [isLoading, setIsLoading] = useState(true)
  const [posts, setPosts] = useState<any>([])

  useEffect(() => {
    const fetchPosts = async () => {
      const { data } = await supabase.from('posts').select()
      setPosts(data)
      setIsLoading(false)
    }

    fetchPosts()
  }, [])

  return isLoading ? <p>Loading</p> : <pre>{JSON.stringify(posts, null, 2)}</pre>
}
```

--------------------------------

### Call Supabase Edge Function - TypeScript (fetch)

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2025-05-17-simplify-backend-with-data-api.mdx

Demonstrates calling a Supabase Edge Function using fetch in TypeScript/TSX. Dependencies: a valid Supabase project reference and an Auth token (Bearer) or service key; inputs: JSON body containing customer_id; outputs: the fetch Response object. Limitations: requires correct CORS/authorization and the function to be deployed at the provided project endpoint.

```tsx
const customerId = 'uuid-of-customer' // Replace with actual customer ID
const projectRef = 'your-project-ref' // e.g. abcdefg.supabase.co
const functionName = 'send-discount'

const response = await fetch(`https://${projectRef}.functions.supabase.co/${functionName}`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer your-access-token`, // From Supabase Auth
  },
  body: JSON.stringify({
    customer_id: customerId,
  }),
})
```

--------------------------------

### Install Supabase Python package

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/realtime/getting_started.mdx

Install the Supabase Python package using pip or conda package managers. Enables Realtime and database functionality for Python applications.

```bash
pip install supabase
```

```bash
conda install -c conda-forge supabase
```

--------------------------------

### Fetch todos in Server Component with createClient - supabase-js (JS/TS)

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/auth/auth-helpers/nextjs.mdx

Server component that fetches todos at build time using createClient from @supabase/supabase-js. Depends on public env vars NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY and returns rendered JSON in JSX. Inputs: none (static fetch); outputs: JSON-rendered data. Limitation: no user/session context is available for authenticated requests when fetching at build time.

```JavaScript
import { createClient } from '@supabase/supabase-js'

export default async function Page() {
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  )

  const { data } = await supabase.from('todos').select()
  return <pre>{JSON.stringify(data, null, 2)}</pre>
}

```

```TypeScript
import { createClient } from '@supabase/supabase-js'

import type { Database } from '@/lib/database.types'

export default async function Page() {
  const supabase = createClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!
  )

  const { data } = await supabase.from('todos').select()
  return <pre>{JSON.stringify(data, null, 2)}</pre>
}

```

--------------------------------

### Query a Vecs collection with filtering (Python)

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/ai/vecs-python-client.mdx

This Python snippet shows how to query a `vecs` collection for similar vectors. It takes a query vector, specifies a limit for the number of records to return, and applies a metadata filter to refine the search, returning relevant matches.

```python
import vecs

docs = vecs.get_or_create_collection(name="docs", dimension=3)

# query the collection filtering metadata for "year" = 2012
docs.query(
    data=[0.4,0.5,0.6],      # required
    limit=1,                         # number of records to return
    filters={"year": {"$eq": 2012}} # metadata filters
)
```

--------------------------------

### Fetch Teams with Related Users Data

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/database/joins-and-nesting.mdx

Retrieves all teams with their associated users using nested queries. Works across multiple SDKs to fetch related data without explicitly joining tables.

```javascript
const { data, error } = await supabase.from('teams').select(`
  id,
  team_name,
  users ( id, name )
`)
```

```dart
final data = await supabase.from('teams').select('id, team_name, users(id, name)');
```

```swift
struct Team: Codable {
  let id: Int
  let name: String
  let users: [User]

  struct User: Codable {
    let id: Int
    let name: String
  }

  enum CodingKeys: String, CodingKey {
    case id, users
    case name = "team_name"
  }
}
let teams [Team] = try await supabase
  .from("teams")
  .select(
    """
      id,
      team_name,
      users ( id, name )
    """
  )
  .execute()
  .value
```

```kotlin
val data = supabase.from("teams").select(Columns.raw("id, team_name, users(id, name)"));
```

```python
data = supabase.from_('teams').select('id, team_name, users(id, name)').execute()
```

--------------------------------

### Fetch Profile Data using GraphQL Query Language

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-03-29-graphql-now-available.mdx

This GraphQL query fetches profile data from a 'profileCollection', typical for a `pg_graphql` generated schema. It retrieves 'id', 'username', 'bio', 'avatarUrl', and 'website' fields from each node, illustrating a GraphQL-centric data fetching approach as an alternative to PostgREST.

```graphql
// using GraphQL

query ProfilesQuery {
    profileCollection {
      edges {
        node {
          id
          username
          bio
          avatarUrl
          website
      }
    }
  }
}
```

--------------------------------

### Define Constants for Slack Monitoring in Python

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-08-09-slack-consolidate-slackbot-to-consolidate-messages.mdx

This snippet defines global constants used throughout the script, such as the delay for scanning new channels (hourly) and the buffer size for fetching messages from Slack API.

```python
SCAN_CHANNELS_DELAY = 3600.0
BUFFER_SIZE = 20
```

--------------------------------

### Fetch 'todos' data from Supabase API using cURL (Terminal)

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/api/quickstart.mdx

This cURL command demonstrates how to fetch data from the Supabase API's `/rest/v1/todos` endpoint. It requires substituting `<PROJECT_REF>` with the project's reference and `<ANON_KEY>` with the anonymous key for authentication. The command sends an HTTP GET request with necessary API key headers.

```bash
curl 'https://<PROJECT_REF>.supabase.co/rest/v1/todos' \
-H "apikey: <ANON_KEY>" \
-H "Authorization: Bearer <ANON_KEY>"
```

--------------------------------

### Fetch Supabase Notes in SvelteKit Load Function

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/auth/server-side/sveltekit.mdx

This JavaScript snippet demonstrates how to fetch 'notes' from a Supabase database within a SvelteKit `load` function. It selects 'id' and 'note' columns, orders them by 'id', and returns an object containing the notes array, defaulting to an empty array if no data is found. It requires an initialized Supabase client.

```javascript
const { data: notes } = await supabase.from('notes').select('id,note').order('id')
  return { notes: notes ?? [] }
```

--------------------------------

### Initialize Supabase client - Python

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/realtime/getting_started.mdx

Create a Supabase client instance using the create_client function with your project URL and key. Establishes connection to Supabase backend for Python applications.

```python
from supabase import create_client, Client

url: str = "https://<project>.supabase.co"
key: str = "<anon_key or sb_publishable_key>"
supabase: Client = create_client(url, key)
```

--------------------------------

### Fetch 'todos' data using Supabase client libraries

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/api/quickstart.mdx

These code snippets demonstrate how to query the 'todos' table using various Supabase client libraries. They all perform a `SELECT` operation to retrieve all data from the 'todos' table, abstracting the API call details.

```javascript
const { data, error } = await supabase.from('todos').select()
```

```dart
final data = await supabase.from('todos').select('*');
```

```python
response = supabase.table('todos').select("*").execute()
```

```swift
let response = try await supabase.from("todos").select()
```

--------------------------------

### Save Roboflow Inference Predictions to Supabase with Python

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/ai/integrations/roboflow.mdx

This Python code demonstrates how to connect to a Supabase database and insert object detection predictions into a table. It retrieves Supabase URL and key from environment variables and saves the filename and prediction results.

```python
import os
from supabase import create_client, Client

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

result = supabase.table('predictions') \
    .insert({"filename": image, "predictions": predictions}) \
    .execute()
```

--------------------------------

### Run Object Detection Inference on an Image with Python

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/ai/integrations/roboflow.mdx

This Python snippet uses the `inference_sdk` to connect to a local Roboflow Inference server and perform object detection on a specified image. It requires a model ID and Roboflow API key, printing the predictions to the console upon completion.

```python
from inference_sdk import InferenceHTTPClient

image = "example.jpg"
MODEL_ID = "rock-paper-scissors-sxsw/11"

client = InferenceHTTPClient(
    api_url="http://localhost:9001",
    api_key="ROBOFLOW_API_KEY"
)
with client.use_model(MODEL_ID):
    predictions = client.infer(image)

print(predictions)
```

--------------------------------

### Fetch and Display Posts as Links with Next.js Server Component

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-11-17-fetching-and-caching-supabase-data-in-next-js-server-components.mdx

This Next.js Server Component fetches `id` and `title` for all posts from Supabase. It then maps over the posts to render a list of `<Link />` components, each navigating to a dedicated page for a specific post. Includes basic error handling for when no posts are found.

```tsx
import Link from 'next/link'
import supabase from '../../utils/supabase'

export default async function Posts() {
  const { data: posts } = await supabase.from('posts').select('id, title')

  if (!posts) {
    return <p>No posts found.</p>
  }

  return posts.map((post) => (
    <p key={post.id}>
      <Link href={`/static/${post.id}`}>{post.title}</Link>
    </p>
  ))
}
```

--------------------------------

### Fetch Supabase Data in Next.js Client Component

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/auth/auth-helpers/nextjs.mdx

This example demonstrates how to fetch data from Supabase within a Next.js Client Component. It utilizes `createClientComponentClient` to initialize the Supabase client and `useEffect` to perform an asynchronous data fetch when the component mounts, updating the component's state with the retrieved data. Both JavaScript and TypeScript versions are provided.

```jsx
'use client'

import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useEffect, useState } from 'react'

export default function Page() {
  const [todos, setTodos] = useState()
  const supabase = createClientComponentClient()

  useEffect(() => {
    const getData = async () => {
      const { data } = await supabase.from('todos').select()
      setTodos(data)
    }

    getData()
  }, [])

  return todos ? <pre>{JSON.stringify(todos, null, 2)}</pre> : <p>Loading todos...</p>
}
```

```tsx
'use client'

import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useEffect, useState } from 'react'

import type { Database } from '@/lib/database.types'

type Todo = Database['public']['Tables']['todos']['Row']

export default function Page() {
  const [todos, setTodos] = useState<Todo[] | null>(null)
  const supabase = createClientComponentClient<Database>()

  useEffect(() => {
    const getData = async () => {
      const { data } = await supabase.from('todos').select()
      setTodos(data)
    }

    getData()
  }, [])

  return todos ? <pre>{JSON.stringify(todos, null, 2)}</pre> : <p>Loading todos...</p>
}
```

--------------------------------

### Configure fetch-retry options (JavaScript)

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/api/automatic-retries-in-supabase-js.mdx

Shows how to customize fetch-retry options like retries, retryDelay (exponential backoff), and which HTTP statuses trigger retries. Dependencies: fetch-retry and a fetch API. Inputs: numeric limits and a retry predicate; Output: a customized fetchWithRetry function. Limitation: you should restrict retries to transient errors to avoid exhausting server resources.

```javascript
const fetchWithRetry = fetchRetry(fetch, {
  retries: 3, // Number of retry attempts
  retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000), // Exponential backoff
  retryOn: [520], // Retry only on Cloudflare errors
})
```

--------------------------------

### Interact with Supabase API to fetch data (JavaScript and cURL)

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/api/creating-routes.mdx

Demonstrates how to fetch data from a Supabase API route using both the JavaScript client library and direct cURL requests. Both methods require the Supabase URL and a publishable API key for authentication.

```javascript
// Initialize the JS client
import { createClient } from '@supabase/supabase-js'
const supabase = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)

// Make a request
const { data: todos, error } = await supabase.from('todos').select('*')
```

```bash
# Append /rest/v1/ to your URL, and then use the table name as the route
curl '<SUPABASE_URL>/rest/v1/todos' \
-H "apikey: <SUPABASE_PUBLISHABLE_KEY>" \
-H "Authorization: Bearer <SUPABASE_PUBLISHABLE_KEY>"
```

--------------------------------

### Fetch and Display Single Post Statically with Next.js Dynamic Route (Initial)

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-11-17-fetching-and-caching-supabase-data-in-next-js-server-components.mdx

This Next.js Server Component handles a dynamic route to fetch and display a single post based on its `id` parameter. It queries Supabase for the specific post and uses `notFound()` from `next/navigation` to handle cases where the post does not exist.

```tsx
import supabase from '../../../utils/supabase'
import { notFound } from 'next/navigation'

export default async function Post({ params: { id } }: { params: { id: string } }) {
  const { data } = await supabase.from('posts').select().match({ id }).single()

  if (!data) {
    notFound()
  }

  return <pre>{JSON.stringify(data, null, 2)}</pre>
}
```

--------------------------------

### Fetch and Display Single Post Dynamically on Every Request (Next.js TypeScript)

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-11-17-fetching-and-caching-supabase-data-in-next-js-server-components.mdx

This Next.js component fetches and displays a single post by ID from Supabase, behaving like a fully dynamic server-rendered page. Setting `revalidate = 0` guarantees that the latest data is fetched on every request, making it suitable for content that needs to be absolutely up-to-date. `generateStaticParams` is still used for defining possible routes, but the individual page content is always fresh.

```tsx
import supabase from '../../../utils/supabase'
import { notFound } from 'next/navigation'

export const revalidate = 0

export async function generateStaticParams() {
  const { data: posts } = await supabase.from('posts').select('id')

  return posts?.map(({ id }) => ({
    id,
  }))
}

export default async function Post({ params: { id } }: { params: { id: string } }) {
  const { data: post } = await supabase.from('posts').select().match({ id }).single()

  if (!post) {
    notFound()
  }

  return <pre>{JSON.stringify(post, null, 2)}</pre>
}
```

--------------------------------

### Fetch Data Client-side in Next.js Client Component with React Query

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2024-01-12-react-query-nextjs-app-router-cache-helpers.mdx

This Next.js Client Component illustrates traditional client-side data fetching using `useQuery` from `@supabase-cache-helpers/postgrest-react-query`. It initializes a Supabase browser client and uses `useQuery` to fetch country data based on the provided ID. The component gracefully handles loading states and displays error messages if the data fetch fails or the country is not found.

```tsx
'use client'

import useSupabaseBrowser from '@/utils/supabase-browser'
import { getCountryById } from '@/queries/get-country-by-id'
import { useQuery } from '@supabase-cache-helpers/postgrest-react-query'

export default function CountryPage({ params }: { params: { id: number } }) {
  const supabase = useSupabaseBrowser()
  const { data: country, isLoading, isError } = useQuery(getCountryById(supabase, params.id))

  if (isLoading) {
    return <div>Loading...</div>
  }

  if (isError || !country) {
    return <div>Error</div>
  }

  return (
    <div>
      <h1>{country.name}</h1>
    </div>
  )
}
```

--------------------------------

### Load Paul Graham's essays as documents using SimpleWebPageReader

Source: https://github.com/supabase/supabase/blob/master/examples/ai/llamaindex/llamaindex.ipynb

This code loads a small dataset of Paul Graham's essays from GitHub using LlamaIndex's `SimpleWebPageReader`. It fetches the text content of specified essays and converts them into `Document` objects for further processing with LlamaIndex.

```python
essays = [
    'paul_graham_essay.txt'
]
documents = SimpleWebPageReader().load_data([f'https://raw.githubusercontent.com/supabase/supabase/master/examples/ai/llamaindex/data/{essay}' for essay in essays])
print('Document ID:', documents[0].doc_id, 'Document Hash:', documents[0].hash)
```

--------------------------------

### Fetch and Display Single Post with Static Revalidation (Next.js TypeScript)

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-11-17-fetching-and-caching-supabase-data-in-next-js-server-components.mdx

This component fetches a single post by ID from Supabase and displays its details. It leverages `generateStaticParams` to pre-render dynamic routes and `revalidate = 60` for caching, providing the benefits of static pages with periodic data updates. The `notFound` function from `next/navigation` handles cases where a post is not found.

```tsx
import supabase from '../../../utils/supabase'
import { notFound } from 'next/navigation'

export const revalidate = 60

export async function generateStaticParams() {
  const { data: posts } = await supabase.from('posts').select('id')

  return posts?.map(({ id }) => ({
    id,
  }))
}

export default async function Post({ params: { id } }: { params: { id: string } }) {
  const { data: post } = await supabase.from('posts').select().match({ id }).single()

  if (!post) {
    notFound()
  }

  return <pre>{JSON.stringify(post, null, 2)}</pre>
}
```

--------------------------------

### Identify Near-Duplicate Reviews with Python Embeddings

Source: https://github.com/supabase/supabase/blob/master/examples/ai/semantic_text_deduplication.ipynb

This Python script iterates through a dataset of reviews, queries a vector database (e.g., Pinecone) for the 5 most similar reviews based on their embeddings, and prints pairs of reviews that are considered near-duplicates (distance between 0.01 and 0.17). It includes a restriction to process reviews under 500 characters for readability and filters out the query review itself. The script assumes `tqdm` for progress tracking and a `reviews` object (likely a vector database client) with `fetch` and `query` methods.

```python
for ix, text in tqdm(enumerate(data['text'])):

    # Load the next row from the dataset
    query_results = reviews.fetch(ids=[f'{ix}'])
    
    (query_id, query_embedding, query_meta) = query_results[0]

    # Retrieve the original text from the row's metadata
    query_text = query_meta["text"]

    # To keep the output easy to read quickly, we'll restrict reviews to < 500 characters
    # In the real-world you would not include this restriction
    if len(query_text) < 500:

        # Query the review embeddings for the most similar 5 reviews
        top_5 = reviews.query(
            query_vector=query_embedding,
            limit = 5,
            include_metadata= True,
            include_value=True
        )

        # For each result
        for result_id, result_distance, result_meta in top_5[1:]:
            
            result_text = result_meta["text"]

            if (
                # Since our query embedding is in the collection, the nearest result
                # is always itself with a distance of 0. We exclude that record and 
                # review any others with a distance < 0.17
                0.01 < abs(result_distance) < 0.17
                and len(result_text) < 500
                and query_id < result_id
            ):
                print(
                    "query_id:", query_id,
                    "\t", "result_id:", result_id,
                    "\t", "distance", round(result_distance, 4),
                    "\n\n", "Query Text",
                    "\n\n", query_meta["text"],
                    "\n\n", "Result Text",
                    "\n\n", result_meta["text"],
                    "\n", "-" * 80
                )
```

--------------------------------

### Create Realtime channel - Python

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/realtime/getting_started.mdx

Create a named Realtime channel with configuration parameters for Python applications. Enables real-time message subscription within the specified channel.

```python
# Create a channel with a descriptive topic name
channel = supabase.channel('room:lobby:messages', params={config={private= True }})
```

--------------------------------

### Fetch Single Article from Queue for Processing (TypeScript)

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2025-09-12-processing-large-jobs-with-edge-functions.mdx

Retrieves a single unprocessed article from the `nfl_queue` table, ordered by creation date. This strategy ensures that Edge Functions process one item at a time, staying within typical timeout limits.

```tsx
const { data } = await supabase
  .from('nfl_queue')
  .select('id, url')
  .eq('processed', false)
  .order('created_at')
  .limit(1)
```

--------------------------------

### Retrieve All Records from PostgreSQL Array Table

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/database/arrays.mdx

This SQL query fetches all columns and rows from the `arraytest` table. It is used to verify the successful insertion and current state of array data within the table.

```SQL
select * from arraytest;
```

--------------------------------

### Query data using supabase-js client (JavaScript)

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/api/automatic-retries-in-supabase-js.mdx

Performs a basic select query using the configured supabase client. Inputs: table name and optional query filters; Outputs: data or error logged to console. Limitation: retry behavior depends on the fetch wrapper injected into the client (see previous snippets).

```javascript
async function fetchData() {
  const { data, error } = await supabase.from('your_table').select('*')

  if (error) {
    console.error('Error fetching data:', error)
  } else {
    console.log('Fetched data:', data)
  }
}

fetchData()
```

--------------------------------

### Fetch and sort Supabase data with useInfiniteQuery in React

Source: https://github.com/supabase/supabase/blob/master/apps/ui-library/content/docs/infinite-query-hook.mdx

This example demonstrates using the `useInfiniteQuery` hook to fetch products from a Supabase table, sorting them by the 'created_at' column in descending order. It shows how to render the fetched data and includes a button to load the next page of results.

```tsx
const { data, fetchNextPage } = useInfiniteQuery({
  tableName: 'products',
  columns: '*',
  pageSize: 10,
  trailingQuery: (query) => query.order('created_at', { ascending: false })
})

return (
  <div>
    {data.map((item) => (
      <ProductCard key={item.id} product={item} />
    ))}
    <Button onClick={fetchNextPage}>Load more products</Button>
  </div>
)
```

--------------------------------

### Import Supabase and Mixpeek clients (Python)

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/ai/examples/mixpeek-video-search.mdx

Initialize Python imports and load required environment variables for Supabase and Mixpeek API keys. These values must be set in the environment before running the application. No network calls are made in this snippet; it only prepares client credentials.

```python
from supabase import create_client, Client
from mixpeek import Mixpeek
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_API_KEY")
MIXPEEK_API_KEY = os.getenv("MIXPEEK_API_KEY")
```

--------------------------------

### Install vecs Python Client

Source: https://github.com/supabase/supabase/blob/master/examples/ai/vector_hello_world.ipynb

Installs the `vecs` Python library using pip, which is used for managing vector stores in PostgreSQL with the pgvector extension. Ensure Python 3.7+ is installed before running.

```python
pip install vecs
```

--------------------------------

### Server-side data fetching with RLS in SvelteKit

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/auth/auth-helpers/sveltekit.mdx

Implements protected server-side data fetching with automatic session validation and redirect. The load function checks for active session and fetches data server-side, ensuring RLS policies are enforced before data reaches the client. Returns both user and table data to the page component.

```svelte
<!-- src/routes/profile/+page.svelte -->
<script lang="ts">
  export let data

  let { user, tableData } = data
  $: ({ user, tableData } = data)
</script>

<div>Protected content for {user.email}</div>
<pre>{JSON.stringify(tableData, null, 2)}</pre>
<pre>{JSON.stringify(user, null, 2)}</pre>
```

```typescript
// src/routes/profile/+page.ts
import { redirect } from '@sveltejs/kit'

export const load = async ({ parent }) => {
  const { supabase, session } = await parent()
  if (!session) {
    redirect(303, '/')
  }
  const { data: tableData } = await supabase.from('test').select('*')

  return {
    user: session.user,
    tableData,
  }
}
```

--------------------------------

### Full Next.js Dynamic Route with Static Param Generation and Supabase Fetching

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-11-17-fetching-and-caching-supabase-data-in-next-js-server-components.mdx

This complete Next.js Server Component for a dynamic route combines static path generation with individual post fetching. It uses `generateStaticParams` to pre-render pages for all posts at build time, and the default `Post` component then fetches the specific post data using Supabase.

```tsx
import supabase from '../../../utils/supabase'
import { notFound } from 'next/navigation'

export async function generateStaticParams() {
  const { data: posts } = await supabase.from('posts').select('id')

  return posts?.map(({ id }) => ({
    id,
  }))
}

export default async function Post({ params: { id } }: { params: { id: string } }) {
  const { data: post } = await supabase.from('posts').select().match({ id }).single()

  if (!post) {
    notFound()
  }

  return <pre>{JSON.stringify(post, null, 2)}</pre>
}
```

--------------------------------

### Fetch PostgreSQL EXPLAIN plan using `supabase-js`

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/troubleshooting/understanding-postgresql-explain-output-Un9dqX.mdx

This JavaScript example shows how to programmatically retrieve a PostgreSQL `EXPLAIN` execution plan using the `supabase-js` client library. It utilizes the `explain()` method with `analyze: true` and `verbose: true` options for detailed, actual execution statistics, requiring prior enablement of performance debugging.

```javascript
const { data, error } = await supabase
  .from('countries')
  .select()
  .explain({analyze:true,verbose:true})
```

--------------------------------

### Create a new vector collection with Vecs (Python)

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/ai/vecs-python-client.mdx

This Python snippet initializes the `vecs` client to connect to a local PostgreSQL database and creates or retrieves a vector collection named 'docs' with a specified dimension. It sets up the foundation for storing and managing vector embeddings.

```python
import vecs

# create vector store client
vx = vecs.create_client("postgresql://postgres:postgres@localhost:54322/postgres")

# create a collection of vectors with 3 dimensions
docs = vx.get_or_create_collection(name="docs", dimension=3)
```

--------------------------------

### Fetch Queued User Interactions for Batch Processing

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2025-09-12-processing-large-jobs-with-edge-functions.mdx

Retrieves a batch of up to 100 unprocessed user interactions from a Supabase table. This allows a separate processor to handle multiple interactions efficiently, ensuring UI responsiveness.

```typescript
const { data: interactions } = await supabase
  .from('interaction_queue')
  .select('*')
  .eq('processed', false)
  .limit(100)
```

--------------------------------

### REST API Call for Teams with Users

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/database/joins-and-nesting.mdx

HTTP GET request to Supabase REST API using query parameters for nested data selection. Provides a direct URL-based approach to fetch related data.

```bash
GET https://[REF].supabase.co/rest/v1/teams?select=id,team_name,users(id,name)
```

--------------------------------

### Import Python Libraries and Define Database Connection String

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/ai/examples/semantic-image-search-amazon-titan.mdx

Imports essential Python modules for AWS interactions, vector operations, JSON handling, base64 encoding, and image plotting. Defines the PostgreSQL database connection string for Supabase.

```python
import sys
import boto3
import vecs
import json
import base64
from matplotlib import pyplot as plt
from matplotlib import image as mpimg
from typing import Optional

DB_CONNECTION = "postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres"
```

--------------------------------

### Install Vecs (Python)

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/ai/google-colab.mdx

Installs the vecs package into the Colab Python environment using pip. Requires network access and pip-enabled runtime. Outputs the vecs package available for import in subsequent notebook cells.

```python
pip install vecs

```

--------------------------------

### Invoke Supabase Edge Function using JavaScript Fetch API

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/functions/quickstart.mdx

This JavaScript example demonstrates how to invoke a Supabase Edge Function by directly making an HTTP POST request using the native Fetch API. It constructs the request with the function's URL, required headers for authorization and content type, and a JSON stringified body.

```javascript
const response = await fetch('https://[YOUR_PROJECT_ID].supabase.co/functions/v1/hello-world', {
  method: 'POST',
  headers: {
    Authorization: 'Bearer YOUR_ANON_KEY',
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ name: 'Fetch' }),
})

const data = await response.json()
console.log(data)
```

--------------------------------

### GET /rest/v1/todos

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/api/creating-routes.mdx

Retrieve all records from the 'todos' table. This endpoint allows you to fetch a list of all tasks currently stored in your database.

```APIDOC
## GET /rest/v1/todos

### Description
Retrieve all records from the 'todos' table. This endpoint allows you to fetch a list of all tasks currently stored in your database.

### Method
GET

### Endpoint
/rest/v1/todos

### Headers
- **apikey** (string) - Required - Your Supabase project's anonymous key.
- **Authorization** (string) - Required - Bearer token, typically the same as the apikey for anonymous access.

### Parameters
#### Query Parameters
- **select** (string) - Optional - Columns to select, e.g., `select=id,task`. Defaults to `*`.
- **order** (string) - Optional - Column to order by, e.g., `order=created_at.desc`. (PostgREST syntax)
- **limit** (integer) - Optional - Maximum number of rows to return.
- **[filter_column]** (string) - Optional - Filter by column value, e.g., `id=eq.1` or `task=ilike.*buy*`. (PostgREST syntax)

### Request Example
```bash
curl '<SUPABASE_URL>/rest/v1/todos' \
-H "apikey: <SUPABASE_PUBLISHABLE_KEY>" \
-H "Authorization: Bearer <SUPABASE_PUBLISHABLE_KEY>"
```

### Response
#### Success Response (200 OK)
- **id** (integer) - The unique identifier of the todo item.
- **task** (string) - The description of the todo item.

#### Response Example
```json
[
  {
    "id": 1,
    "task": "Learn Supabase"
  },
  {
    "id": 2,
    "task": "Build an app"
  }
]
```
```

--------------------------------

### Add vector embeddings to a Vecs collection (Python)

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/ai/vecs-python-client.mdx

This Python code demonstrates how to insert multiple vector embeddings into an existing `vecs` collection using the `upsert()` method. Each vector includes a unique ID, its numerical embedding, and associated metadata for filtering and search.

```python
import vecs

# create vector store client
docs = vecs.get_or_create_collection(name="docs", dimension=3)

# a collection of vectors with 3 dimensions
vectors=[
  ("vec0", [0.1, 0.2, 0.3], {"year": 1973}),
  ("vec1", [0.7, 0.8, 0.9], {"year": 2012})
]

# insert our vectors
docs.upsert(vectors=vectors)
```

--------------------------------

### Fetch Sidebar Data with React Server Components

Source: https://github.com/supabase/supabase/blob/master/apps/design-system/content/docs/components/sidebar.mdx

Demonstrates a data fetching strategy for sidebar menus using React Server Components. It includes a skeleton component for loading states, an async server component to fetch project data, and integrates them using React Suspense for a dynamic user experience.

```tsx
function NavProjectsSkeleton() {
  return (
    <SidebarMenu>
      {Array.from({ length: 5 }).map((_, index) => (
        <SidebarMenuItem key={index}>
          <SidebarMenuSkeleton showIcon />
        </SidebarMenuItem>
      ))}
    </SidebarMenu>
  )
}
```

```tsx
async function NavProjects() {
  const projects = await fetchProjects()

  return (
    <SidebarMenu>
      {projects.map((project) => (
        <SidebarMenuItem key={project.name}>
          <SidebarMenuButton asChild>
            <a href={project.url}>
              <project.icon />
              <span>{project.name}</span>
            </a>
          </SidebarMenuButton>
        </SidebarMenuItem>
      ))}
    </SidebarMenu>
  )
}
```

```tsx
function AppSidebar() {
  return (
    <Sidebar>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Projects</SidebarGroupLabel>
          <SidebarGroupContent>
            <React.Suspense fallback={<NavProjectsSkeleton />}>
              <NavProjects />
            </React.Suspense>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}
```

--------------------------------

### Access Request Headers and Cookies in PostgreSQL Pre-Request Function

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/api/securing-your-api.mdx

These SQL examples show how to retrieve information about the current API request within a PostgreSQL function. `current_setting('request.headers', true)::json` fetches all request headers as a JSON object, while `->>'user-agent'` can extract specific header values. Similarly, `current_setting('request.cookies', true)::json` accesses all cookies.

```sql
-- To get all the headers sent in the request
SELECT current_setting('request.headers', true)::json;

-- To get a single header, you can use JSON arrow operators
SELECT current_setting('request.headers', true)::json->>'user-agent';

-- Access Cookies
SELECT current_setting('request.cookies', true)::json;
```

--------------------------------

### Close Supabase Realtime Client Socket in Python

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2024-08-16-python-support.mdx

This Python example shows how to explicitly close the socket connection of an `AsyncRealtimeClient` using its new `close()` method. After connecting to the Realtime service and subscribing to a channel, the `await client.close()` line ensures the connection is terminated, providing developers with finer control over the Realtime client's connection lifecycle.

```python
import os
from realtime import AsyncRealtimeClient

def callback1(payload):
    print("Callback 1: ", payload)

SUPABASE_ID: str = os.environ.get("SUPABASE_ID")
API_KEY: str = os.environ.get("SUPABASE_KEY")

URL: str = f"wss://{SUPABASE_ID}.supabase.co/realtime/v1/websocket"

client = AsyncRealtimeClient(URL, API_KEY)
await client.connect()

channel_1 = s.channel("realtime:public:sample")
channel_1.subscribe().on_postgres_changes("INSERT", callback1)

await client.listen()
await client.close()

```

--------------------------------

### Query Specific Elements and Length of PostgreSQL Arrays

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/database/arrays.mdx

These examples demonstrate how to query and access array data. The SQL snippet shows selecting the first element and the total length of an array, while JavaScript and Swift snippets illustrate retrieving the entire array column using the Supabase client.

```SQL
SELECT textarray[1], array_length(textarray, 1) FROM arraytest;
```

```JavaScript
const { data, error } = await supabase.from('arraytest').select('textarray')
console.log(JSON.stringify(data, null, 2))
```

```Swift
struct Response: Decodable {
  let textarray: [String]
}

let response: [Response] = try await supabase.from("arraytest").select("textarray").execute().value
dump(response)
```

--------------------------------

### Install Supabase Library for Python Flask

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2023-11-21-oauth2-login-python-flask-apps.mdx

Installs the `supabase` Python library using pip, which is necessary for integrating Supabase services, including authentication, into a Flask application.

```bash
pip install supabase
```

--------------------------------

### Install Poetry and Initialize Python Project

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/ai/examples/image-search-openai-clip.mdx

Install Poetry package manager and create a new Python project with Poetry initialization. Poetry provides dependency management and packaging for Python applications.

```shell
pip install poetry
```

```shell
poetry new image-search
```

--------------------------------

### Secure Client-side Data Fetching with Supabase RLS in Next.js

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/auth/auth-helpers/nextjs-pages.mdx

This example demonstrates secure client-side data fetching using Supabase Row Level Security (RLS) in a Next.js application. It utilizes `useSupabaseClient` and `useUser` hooks to ensure data is fetched only after a user is authenticated, showcasing conditional rendering for auth UI and displaying fetched data.

```jsx
import { Auth } from '@supabase/auth-ui-react'
import { ThemeSupa } from '@supabase/auth-ui-shared'
import { useUser, useSupabaseClient } from '@supabase/auth-helpers-react'
import { useEffect, useState } from 'react'

const LoginPage = () => {
  const supabaseClient = useSupabaseClient()
  const user = useUser()
  const [data, setData] = useState()

  useEffect(() => {
    async function loadData() {
      const { data } = await supabaseClient.from('test').select('*')
      setData(data)
    }
    // Only run query once user is logged in.
    if (user) loadData()
  }, [user])

  if (!user)
    return (
      <Auth
        redirectTo="http://localhost:3000/"
        appearance={{ theme: ThemeSupa }}
        supabaseClient={supabaseClient}
        providers={['google', 'github']}
        socialLayout="horizontal"
      />
    )

  return (
    <>
      <button onClick={() => supabaseClient.auth.signOut()}>Sign out</button>
      <p>user:</p>
      <pre>{JSON.stringify(user, null, 2)}</pre>
      <p>client-side data fetching with RLS</p>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </>
  )
}

export default LoginPage
```

--------------------------------

### Retrieve Data from Brick Repository (Dart)

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2024-10-08-offline-first-flutter-apps.mdx

This Dart example shows how to fetch data from the Brick repository using a `Query`. It retrieves `User` models where the 'name' field is 'Thomas'. Brick's DSL queries are translated for both local and remote data sources.

```dart
await Repository().get<User>(query: Query.where('name', 'Thomas'));
```

--------------------------------

### Convert Unix Timestamp to ISO String in Python

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-08-09-slack-consolidate-slackbot-to-consolidate-messages.mdx

The `ts_to_strtime` function converts a Unix timestamp (given as an integer) into an ISO 8601 formatted datetime string. This conversion ensures compatibility with PostgreSQL datetime fields.

```python
def ts_to_strtime(ts):
    """_summary_
        Converts the UNIX time in timestamp to ISO format.
    Args:
        ts (int): TS datetime

    Returns:
        str: ISO format datetime string for compatibility with Postgres.
    """
    aux_ts = int(ts)
    return str(datetime.utcfromtimestamp(aux_ts).isoformat())
```

--------------------------------

### Generate Pseudorandom Numeric IDs in Python

Source: https://github.com/supabase/supabase/blob/master/apps/www/_blog/2022-09-08-choosing-a-postgres-primary-key.mdx

This Python function uses `random.randrange` to generate numeric IDs for users. While seemingly functional, it highlights the issue of using pseudorandom number generators for sensitive IDs, as they can be predictable or prone to collisions if not properly seeded.

```python
from random import randrange
from models import User
MAX_RANDOM_USER_ID = 1_000_000_000
def create_user():
    """
    Add new user to the database
    """
    user_id = randrange(1, MAX_RANDOM_USER_ID)
    user = User(id=user_id, email="new@example.com", name="new user")
    db.save(user)
```

--------------------------------

### Client-side data fetching with RLS in SvelteKit

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/auth/auth-helpers/sveltekit.mdx

Demonstrates fetching data client-side with Row Level Security using supabaseClient from PageData. The query only executes after the session is defined client-side, ensuring RLS policies are properly applied. Uses reactive statement to trigger data loading when session becomes available.

```svelte
<script lang="ts">
  export let data

  let loadedData = []
  async function loadData() {
    const { data: result } = await data.supabase.from('test').select('*').limit(20)
    loadedData = result
  }

  $: if (data.session) {
    loadData()
  }
</script>

{#if data.session}
<p>client-side data fetching with RLS</p>
<pre>{JSON.stringify(loadedData, null, 2)}</pre>
{/if}
```

--------------------------------

### Overwrite File with Upsert Option - Python

Source: https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/storage/uploads/standard-uploads.mdx

Shows how to enable file overwriting in Python by passing a dictionary with upsert set to true. This allows replacing an existing file at the specified path.

```python
response = supabase.storage.from_('bucket_name').upload('file_path', file, {
  'upsert': 'true',
})
```