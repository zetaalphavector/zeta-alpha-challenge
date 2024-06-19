# 1. Chunk paginator

Sometimes it's better to spreaad out the load applied to a search engine by requesting less results than wanted. The requester will still want to get the number of hits they have requested. Consider a searcher class:

```python
class Client:
    def __init__(self, n_list: int):
        self.hits = [str(i) for i in range(n_list)]

    def search(self, client_page: int, client_page_size: int) -> list:
        return self.hits[client_page * client_page_size: (client_page + 1) * client_page_size]

class Searcher:
    def __init__(self, client: Client):
        self.client
    
    def search(self, page: int, page_size: int) -> list:
        pass
```

where the `Client` class simulates the search engine and the `Searcher` class  is the one exposed to the user.

We want to be able to set any `page_size` value in the `Searcher` while keeping the `page_sie` value in the `Client` fixed at `M`.

**Examples**:

- `page=1, page_size=120` with `M=25`
- `page=2, page_size=120` with `M=25`
- `page=1, page_size=22` with `M=10`
- `page=2, page_size=22` with `M=10`
- `page=3, page_size=22` with `M=10`
- `page=4, page_size=22` with `M=10`
- `page=5, page_size=22` with `M=10`
- `page=1, page_size=200` with `M=50`
- `page=1, page_size=50` with `M=200`
- `page=2, page_size=50` with `M=200`
- `page=3, page_size=50` with `M=200`
- `page=4, page_size=50` with `M=200`

## Refactoring

Can you think of a structure that can be reused for any `Client` and `Searcher` class? what are the main components?

# 2. Window paginator

In other cases, such as in rerankers, the searcher will need to look at more than the requested number of hits to build the final ordering that is returned to the user. Imagine the number of hits that we need to retrieve from the `Client` to be `W`. Create a solution for this.

**Examples**:
- `page=1, page_size=10` with `W=50`
- `page=2, page_size=10` with `W=50`
- `page=3, page_size=10` with `W=50`
- `page=4, page_size=10` with `W=50`
- `page=5, page_size=10` with `W=50`
- `page=6, page_size=10` with `W=50`
- `page=7, page_size=10` with `W=50`

What should happen if we keep requesting more pages beyond `W`?