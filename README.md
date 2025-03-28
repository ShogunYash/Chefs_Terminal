# India Terminal 2025 – A Competition by Citadel, Citadel Securities and Coorelation One

This repository contains the algorithmic strategy developed for the **India Terminal 2025** competition. Organized by Citadel, Citadel Securities, and Coorelation One, this challenge pushes the boundaries of competitive gaming and algorithmic decision-making.

## Overview

The algorithm is designed for a terminal game where the primary objective is to optimize both defensive and offensive strategies through advanced probability modeling, a custom ML-inspired scoring mechanism, and efficient pathfinding. It smartly balances resource management and unit placement while adapting in real time to the evolving game state.

## Key Features

- **Probability & ML Decision Framework:**  
  The core of the strategy relies on probabilistic models and a custom sigmoid function to evaluate and choose optimal defense and attack paths. Weight factors are dynamically adjusted based on the game state, resource availability, and enemy positioning. This approach is used to compute a "defense score" and to determine the probability of deploying scouts versus interceptors.

- **Pathfinding Integration:**  
  The algorithm leverages an internal pathfinding module (`game_state.find_path_to_edge`) to calculate safe routes for deploying offensive units. It also analyzes potential funnel openings in the defense line to predict enemy vulnerabilities and to find the best spawning locations for counterattacks.

- **Adaptive Resource Management:**  
  The strategy adapts to both current and predicted future states of enemy resources. It includes mechanisms for removing and upgrading walls and turrets based on health thresholds and in-game events, ensuring a robust defense that evolves with the flow of the game.

- **Dynamic Threat Analysis:**  
  By tracking enemy movements and the effectiveness of previously deployed units, the algorithm continuously updates threat scores. This real-time analysis helps in fine-tuning unit deployment—balancing between offensive scouting and interceptor actions.

## Algorithm Components

### 1. Probability and ML Components

- **Sigmoid-Based Decision Making:**  
  A monotonically decreasing sigmoid function is used to translate defense scores into actionable probabilities. This ensures that decisions on whether to send scouts or interceptors are both smooth and adaptable based on fluctuating game parameters.

- **Weighted Scoring System:**  
  Multiple factors such as incurred damage, support boosts, and potential damage to enemy structures are combined using carefully tuned weights. The scoring system adapts based on the number of scouts, enemy SP (structure points), and other resource-related metrics.

### 2. Pathfinding and Funnel Analysis

- **Pathfinding for Safe Deployment:**  
  The algorithm uses the built-in pathfinding mechanism to determine safe routes from potential spawn locations. This is critical for ensuring that deployed units have a clear, low-risk path to the enemy's side of the field.

- **Funnel Opening Detection:**  
  By analyzing gaps in the defensive line (funnel openings), the algorithm identifies the best strategic positions for both launching attacks and reinforcing defenses.

### 3. Resource and Unit Management

- **Dynamic Unit Placement:**  
  The code evaluates the current game state to decide on the optimal configuration of walls, turrets, and support units. It also considers the removal of weak or redundant defenses to open better pathways for attack units.

- **Continuous Feedback Loop:**  
  The algorithm continuously logs game state changes and adjusts its strategy in subsequent turns. This loop ensures that both offensive and defensive tactics remain responsive to real-time challenges.

## Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/ShogunYash/Chefs_Terminal.git
   cd india-terminal-2025
