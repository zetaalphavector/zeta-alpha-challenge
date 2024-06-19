# 1. Chunk paginator

Sometimes it's better to spreaad out the load applied to a search engine by requesting less results than wanted. The requester will still want to get the number of hits they have requested. Consider a searcher class:

```python
class Client:
    def __init__(self, n_list: int):
        self.hits = [str(i) for i in range(n_list)]

    def search(self, client_page: int, client_page_size: int) -> list:
        return self.hits[(client_page-1) * client_page_size: client_page * client_page_size]

class Searcher:
    def __init__(self, client: Client, max_client_page_size: int):
        self.client = client
        self.max_client_page_size = max_client_page_size
    
    def search(self, page: int, page_size: int) -> list:
        raise NotImplementedError

# Example usage
searcher = Searcher(Client(10000), 25)
print(searcher.search(1, 120)) # Should get [0, 1, ..., 119]
```

where the `Client` class simulates the search engine and the `Searcher` class  is the one exposed to the user.

We want to be able to set any `page_size` value in the `Searcher` while keeping the `client_page_size` value in the `Client` fixed at `max_client_page_size`.

**Examples**:

- `page=1, page_size=120` with `M=25` we should get `[0, 1, ..., 119]`
- `page=2, page_size=120` with `M=25` we should get `[120, 121, ..., 239]`
- `page=1, page_size=22` with `M=10` we should get `[0, 1, ..., 21]`
- `page=2, page_size=22` with `M=10` we should get `[22, 23, ..., 43]`
- `page=3, page_size=22` with `M=10` we should get `[44, 45, ..., 65]`
- `page=4, page_size=22` with `M=10` we should get `[66, 67, ..., 87]`
- `page=5, page_size=22` with `M=10` we should get `[88, 89, ..., 109]`
- `page=1, page_size=200` with `M=50` we should get `[0, 1, ..., 199]`
- `page=1, page_size=50` with `M=200` we should get `[0, 1, ..., 49]`
- `page=2, page_size=50` with `M=200` we should get `[50, 51, ..., 99]`
- `page=3, page_size=50` with `M=200` we should get `[100, 101, ..., 149]`
- `page=4, page_size=50` with `M=200` we should get `[150, 151, ..., 199]`

## Refactoring

Can you think of a structure that can be reused for any `Client` and `Searcher` class? what are the main components?

# 2. Window paginator

In other cases, such as in rerankers, the searcher will need to look at more than the requested number of hits to build the final ordering that is returned to the user. Imagine the number of hits that we need to retrieve from the `Client` to be `W`. Create a solution for this.

**Examples**:
- `page=1, page_size=10` with `W=50` we should get `[0, 1, ..., 49]`
- `page=2, page_size=10` with `W=50` we should get `[50, 51, ..., 99]`
- `page=3, page_size=10` with `W=50` we should get `[100, 101, ..., 149]`
- `page=4, page_size=10` with `W=50` we should get `[150, 151, ..., 199]`
- `page=5, page_size=10` with `W=50` we should get `[200, 201, ..., 249]`
- `page=6, page_size=10` with `W=50` we should get `[250, 251, ..., 299]`
- `page=7, page_size=10` with `W=50` we should get `[300, 301, ..., 349]`

What should happen if we keep requesting more pages beyond `W`?