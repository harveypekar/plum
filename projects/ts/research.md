# Twilight Struggle AI Research

## Existing Projects

### Game Implementations (Open Source)

| Project | Language | Description | URL |
|---------|----------|-------------|-----|
| herbix/TwilightStruggle | Scala | Full game implementation with server/client | https://github.com/herbix/TwilightStruggle |
| aasmith/struggle | Ruby | Rules-enforced game engine | https://github.com/aasmith/struggle |
| trevelyan/ts-blockchain | JavaScript | Full implementation on Saito game engine | https://github.com/trevelyan/ts-blockchain |

### AI Attempts

| Project | Approach | Notes |
|---------|----------|-------|
| TrikkStar/HC_Senior-Thesis | RL agent (senior thesis) | https://github.com/TrikkStar/HC_Senior-Thesis |
| Steam digital version | Learned AI trained on player data | Mixed reception -- decent at realignments, makes bizarre moves elsewhere |
| Jonathan Fanno's solo AI | Heuristic rulebook for physical board game | https://boardgamegeek.com/filepage/102622 |

### Research Gap

No significant published research applying deep RL, AlphaZero-style MCTS, or CFR to Twilight Struggle specifically. This is an open area.

## Why Twilight Struggle Is Hard for AI

- **Imperfect information**: hidden hands, opponent's cards unknown
- **Asymmetric gameplay**: USSR and USA have different cards and strategies
- **Large action space**: card play + operations (influence, coups, realignments) + events
- **Long-term vs short-term tradeoffs**: DEFCON management, space race, scoring timing
- **Stochasticity**: dice rolls for coups/realignments, card draw order
- **Card interactions**: ~110 unique event cards with complex effects

Closer to Poker AI territory (imperfect information) than Chess/Go (perfect information).

## AI Approaches

### Recommended: PPO (Policy Gradient)

- **Why**: A 2025 paper (arxiv.org/abs/2502.08938) across 7000+ training runs found PPO matched or beat CFR-based approaches for imperfect information games
- **Complexity**: Simple to implement with Stable-Baselines3
- **GPU fit**: Tiny model (few MB), trains fast on any GPU
- **Architecture**: game state -> MLP (3-4 hidden layers, 256-512 neurons) -> action probabilities
- **Start here**

### Alternative: CFR (Counterfactual Regret Minimization)

- **Why**: Provably converges to Nash equilibrium in two-player zero-sum games. Gold standard for poker AI (Libratus, Pluribus)
- **Complexity**: Hard to implement, memory-intensive for large game trees
- **GPU fit**: GPU-accelerated CFR runs up to 352x faster than CPU (arxiv.org/abs/2408.14778)
- **Game abstraction required**: TS game tree is too large for tabular CFR; needs deep CFR with neural net function approximation

### Alternative: AlphaZero + Information Set Adaptation

- **Why**: Well-documented approach, proven in many games. Surprisingly strong even for imperfect information (frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2023.1014561)
- **Complexity**: Moderate -- MCTS + small neural net
- **GPU fit**: Small ResNet or MLP, fits easily on 8GB
- **Caveat**: Designed for perfect information; needs adaptation (e.g., determinization or information set MCTS)

### State-of-the-Art: ReBeL (Meta)

- **Why**: Combines RL + search, works for imperfect info games, provably converges to Nash equilibrium
- **Complexity**: Most complex to implement
- **GPU fit**: Fine on 8GB
- **Reference**: ai.meta.com/research/publications/combining-deep-reinforcement-learning-and-search-for-imperfect-information-games/

## Hardware Requirements

Target GPU: RTX 2070 Super (8GB VRAM, CUDA 12.9)

The GPU is **not** the bottleneck. The neural network for any of these approaches is tiny (KB-MB range). The GPU's role is parallelizing self-play game simulations during training. The real bottleneck is game engine simulation speed -- how fast you can play thousands of games.

## Practical Starting Stack

```
Game engine:   Python (OpenSpiel or custom TS implementation)
RL framework:  Stable-Baselines3 (PPO out of the box)
GPU:           RTX 2070 Super (more than enough)
Training:      Self-play
```

## Key References

- PPO vs CFR for imperfect info games: https://arxiv.org/abs/2502.08938
- GPU-Accelerated CFR: https://arxiv.org/abs/2408.14778
- AlphaZero for imperfect info: https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2023.1014561
- ReBeL (Meta): https://ai.meta.com/research/publications/combining-deep-reinforcement-learning-and-search-for-imperfect-information-games/
- Policy gradient for card games: https://www.mdpi.com/2076-3417/15/4/2121
- DeepNash (DeepMind) -- Regularised Nash Dynamics: https://www.nature.com/articles/s41586-023-06004-9
- Ticket to Ride RL (similar problem class): https://ieeexplore.ieee.org/document/10154465

## Open Questions

- [ ] Does OpenSpiel have a Twilight Struggle environment?
- [ ] What game state representation to use? (board state, hand, DEFCON, VP, space race, turn, action round)
- [ ] How to handle the variable action space? (different legal actions each turn depending on hand + board)
- [ ] Train against self-play or against heuristic opponents first?
- [ ] How to encode card events? (one-hot card IDs vs learned embeddings)
