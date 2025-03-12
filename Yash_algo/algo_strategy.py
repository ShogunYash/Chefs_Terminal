# import gamelib
# import random
# import math
# import warnings
# from sys import maxsize
# import json

# class AttackManager:
#     def __init__(self):
#         self.vulnerable_points = []
#         self.best_spawn_location = None
#         self.last_attack_turn = -5  # Track when we last attacked
    
#     def find_vulnerable_areas(self, game_state):
#         """
#         Analyzes the opponent's defense to find vulnerable areas.
#         Returns a list of potential spawn locations ranked by effectiveness.
#         """
#         spawn_locations = []
#         # Check left and right sides of our territory
#         left_spawns = [[i, 0] for i in range(5, 13)]
#         right_spawns = [[i, 0] for i in range(15, 23)]
        
#         all_possible_spawns = left_spawns + right_spawns
        
#         # Evaluate each spawn point by calculating expected damage along path
#         spawn_scores = []
#         for spawn in all_possible_spawns:
#             if game_state.can_spawn(SCOUT, spawn):
#                 path = game_state.find_path_to_edge(spawn)
#                 if not path:
#                     continue
                
#                 # Calculate total damage and number of turns to reach opponent's edge
#                 total_damage = 0
#                 for path_location in path:
#                     attackers = game_state.get_attackers(path_location, 0)
#                     # Calculate damage from each attacker
#                     for attacker in attackers:
#                         if attacker.unit_type == TURRET:
#                             total_damage += attacker.damage_i
                
#                 # Score is inversely proportional to damage (lower damage is better)
#                 if total_damage > 0:
#                     score = 1000 / total_damage
#                 else:
#                     score = 1000  # Perfect path with no damage
                
#                 spawn_scores.append((spawn, score, len(path)))
        
#         # Sort by score (higher is better)
#         spawn_scores.sort(key=lambda x: x[1], reverse=True)
        
#         # Return the top 3 spawn locations
#         return [score[0] for score in spawn_scores[:3]]
    
#     def execute_attack(self, game_state):
#         """
#         Executes the attack strategy:
#         - If we have 7+ MP, send 7 scouts from the best location
#         - Otherwise, send a single interceptor as a distraction
#         """
#         # Find the best spawn locations
#         # best_locations = self.find_vulnerable_areas(game_state)
        
#         # if not best_locations:
#         #     return False  # No valid spawn locations
#         self.best_spawn_location = [10, 3]
#         if game_state.get_resource(MP) < 7:
#             # Send a single interceptor as a distraction
#             game_state.attempt_spawn(INTERCEPTOR, self.best_spawn_location, 1)
#             return False
#         # Launch 7 scouts at once for a coordinated attack
#         MP_nearest_integer = math.floor(game_state.get_resource(MP))
#         game_state.attempt_spawn(SCOUT, self.best_spawn_location, MP_nearest_integer)
#         self.last_attack_turn = game_state.turn_number
#         return True    
    
#     def filter_blocked_locations(self, locations, game_state):
#         """
#         Filter out locations that are blocked by stationary units.
#         """
#         filtered = []
#         for location in locations:
#             if not game_state.contains_stationary_unit(location):
#                 filtered.append(location)
#         return filtered

# class AlgoStrategy(gamelib.AlgoCore):
#     def __init__(self):
#         super().__init__()
#         seed = random.randrange(maxsize)
#         random.seed(seed)
#         gamelib.debug_write('Random seed: {}'.format(seed))
#         self.attack_manager = AttackManager()
#         self.support_locations = [[11,4],[12,4], [13,4],[14,4]]
#         self.spawn = [10,3]
#         # Define multiple funnel openings with corresponding spawn points
#         self.funnels = [
#             {"opening": [[10, 12], [11, 12]]},
#             {"opening": [[5, 12], [6, 12]]},
#             {"opening": [[18, 12], [19, 12]]}
#         ]
#         self.current_funnel_index = 0
#         self.last_funnel_change = 0

#     def on_game_start(self, config):
#         """ 
#         Read in config and perform any initial setup here 
#         """
#         gamelib.debug_write('Configuring your custom algo strategy...')
#         self.config = config
#         global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
#         WALL = config["unitInformation"][0]["shorthand"]
#         SUPPORT = config["unitInformation"][1]["shorthand"]
#         TURRET = config["unitInformation"][2]["shorthand"]
#         SCOUT = config["unitInformation"][3]["shorthand"]
#         DEMOLISHER = config["unitInformation"][4]["shorthand"]
#         INTERCEPTOR = config["unitInformation"][5]["shorthand"]
#         MP = 1
#         SP = 0
#         # This is a good place to do initial setup
#         self.scored_on_locations = []

#     def on_turn(self, turn_state):
#         game_state = gamelib.GameState(self.config, turn_state)
#         gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
#         game_state.suppress_warnings(True)

#         # Rotate funnel every 4 turns
#         if game_state.turn_number % 4 == 0 and game_state.turn_number != self.last_funnel_change:
#             for location in self.funnels[self.current_funnel_index]["opening"]:
#                 game_state.attempt_remove(location)
#             self.current_funnel_index = (self.current_funnel_index + 1) % 3
#             self.last_funnel_change = game_state.turn_number
#             gamelib.debug_write(f"Rotating to funnel {self.current_funnel_index}")

#         # Update defense manager
#         # self.defense_manager.update_threat(self.scored_on_locations)
#         self.scored_on_locations = []
        
#         self.starter_strategy(game_state)
#         game_state.submit_turn()

#     def starter_strategy(self, game_state):
#         """
#         For defense we will use a spread out layout and some interceptors early on.
#         We will place turrets near locations the opponent managed to score on.
#         For offense we will use long range demolishers if they place stationary units near the enemy's front.
#         If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
#         """
#         # First, place basic defenses
#         self.build_defences(game_state)
#         # Use our new attack manager to execute attacks
#         attack_executed = self.attack_manager.execute_attack(game_state)

#     def upgrade_defenses(self, game_state):
#         y = 12
#         current_funnel = self.funnels[self.current_funnel_index]["opening"]
#         # Upgrade turrets and supports
#         game_state.attempt_upgrade([[0, 13], [27, 13]])
#         x = 3
#         while x <= 26:
#             if [x, y] not in current_funnel:
#                 game_state.attempt_upgrade([x, y])
#             x += 4
            
#         game_state.attempt_upgrade(self.support_locations)    

#     def build_defences(self, game_state):
#         """
#         Build defenses with dynamic funnel opening.
#         """
#         y = 12
#         # Skip if this position is part of the current funnel opening
#         current_funnel = self.funnels[self.current_funnel_index]["opening"]
#         # Build a turret line on the front with walls in between
#         x = 3
#         while x < 26:
#             game_state.attempt_spawn(TURRET, [x, y])
#             x += 4

#         # Fill in the gaps with walls, but leave the current funnel open
#         game_state.attempt_spawn(WALL, [[0, 13], [27, 13]])
#         x = 1
#         while x <= 26:               
#             location = [x, y]
#             if location not in current_funnel:
#                 game_state.attempt_spawn(WALL, location)
#             x += 1

#         # Support structures
#         game_state.attempt_spawn(SUPPORT, self.support_locations)

#         if game_state.turn_number > 2:
#             self.upgrade_defenses(game_state)

#     def on_action_frame(self, turn_string):
#         """
#         This is the action frame of the game. This function could be called 
#         hundreds of times per turn and could slow the algo down so avoid putting slow code here.
#         Processing the action frames is complicated so we only suggest it if you have time and experience.
#         Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
#         """
#         # Let's record at what position we get scored on
#         state = json.loads(turn_string)
#         events = state["events"]
#         breaches = events["breach"]
#         for breach in breaches:
#             location = breach[0]
#             unit_owner_self = True if breach[4] == 1 else False
#             # When parsing the frame data directly, 
#             # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
#             if not unit_owner_self:
#                 gamelib.debug_write("Got scored on at: {}".format(location))
#                 self.scored_on_locations.append(location)
#                 gamelib.debug_write("All locations: {}".format(self.scored_on_locations))


# if __name__ == "__main__":
#     algo = AlgoStrategy()
#     algo.start()

import gamelib
import random
import math
import warnings
from sys import maxsize
import json

class AttackManager:
    def __init__(self):
        self.vulnerable_points = []
        self.best_spawn_location = None
        self.last_attack_turn = -5  # Track when we last attacked
    
    def find_vulnerable_areas(self, game_state):
        """
        Analyzes the opponent's defense to find vulnerable areas.
        Returns a list of potential spawn locations ranked by effectiveness.
        """
        spawn_locations = []
        # Check left and right sides of our territory
        left_spawns = [[i, 0] for i in range(5, 13)]
        right_spawns = [[i, 0] for i in range(15, 23)]
        
        all_possible_spawns = left_spawns + right_spawns
        
        # Evaluate each spawn point by calculating expected damage along path
        spawn_scores = []
        for spawn in all_possible_spawns:
            if game_state.can_spawn(SCOUT, spawn):
                path = game_state.find_path_to_edge(spawn)
                if not path:
                    continue
                
                # Calculate total damage and number of turns to reach opponent's edge
                total_damage = 0
                for path_location in path:
                    attackers = game_state.get_attackers(path_location, 0)
                    # Calculate damage from each attacker
                    for attacker in attackers:
                        if attacker.unit_type == TURRET:
                            total_damage += attacker.damage_i
                
                # Score is inversely proportional to damage (lower damage is better)
                if total_damage > 0:
                    score = 1000 / total_damage
                else:
                    score = 1000  # Perfect path with no damage
                
                spawn_scores.append((spawn, score, len(path)))
        
        # Sort by score (higher is better)
        spawn_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return the top 3 spawn locations
        return [score[0] for score in spawn_scores[:3]]
    
    def execute_attack(self, game_state):
        """
        Executes the attack strategy:
        - If we have 7+ MP, send 7 scouts from the best location
        - Otherwise, send a single interceptor as a distraction
        """
        # Find the best spawn locations
        # best_locations = self.find_vulnerable_areas(game_state)
        
        # if not best_locations:
        #     return False  # No valid spawn locations
        
        self.best_spawn_location = [5,8]
        if game_state.get_resource(MP) < 7:
            # Send a single interceptor as a distraction
            game_state.attempt_spawn(INTERCEPTOR, self.best_spawn_location, 1)
            return False
        # Launch 7 scouts at once for a coordinated attack
        MP_nearest_integer = math.floor(game_state.get_resource(MP))
        game_state.attempt_spawn(SCOUT, self.best_spawn_location, MP_nearest_integer)
        self.last_attack_turn = game_state.turn_number
        return True    
    
    def filter_blocked_locations(self, locations, game_state):
        """
        Filter out locations that are blocked by stationary units.
        """
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

class DefenseManager:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        # Initialize each cell with a threat value of 1 (binary 01)
        self.map = [[1 for _ in range(height)] for _ in range(width)]
    
    def update_threat(self, attacked_coords):
        """
        Update the threat map based on attacked coordinates.
        Increment threat for attacked cells, capped at 3 (binary 11).
        Decrement threat for untouched cells, floored at 0 (binary 00).
        """
        for x in range(self.width):
            for y in range(self.height):
                if (x, y) in attacked_coords:
                    self.map[x][y] = min(self.map[x][y] + 1, 3)
                else:
                    self.map[x][y] = max(self.map[x][y] - 1, 0)
    
    def get_high_threat_locations(self):
        """
        Identify cells with threat values >= 2 (binary 10 or 11).
        """
        high_threat_cells = []
        for x in range(self.width):
            for y in range(self.height):
                if self.map[x][y] >= 2:
                    high_threat_cells.append((x, y))
        return high_threat_cells
    
    def compute_center_of_threat(self, high_threat_cells):
        """
        Compute the centroid (average x and y coordinates) of high-threat cells.
        If no high-threat cells exist, return the center of the grid.
        """
        if not high_threat_cells:
            return (self.width // 2, self.height // 2)
        
        sum_x = sum(cell[0] for cell in high_threat_cells)
        sum_y = sum(cell[1] for cell in high_threat_cells)
        
        return (sum_x // len(high_threat_cells), sum_y // len(high_threat_cells))
    
    def calculate_defense_radius(self, high_threat_cells, center):
        """
        Calculate the optimal radius to cover high-threat cells.
        Use average distance from the center plus a margin to avoid outliers.
        """
        if not high_threat_cells:
            return 0
        
        distances = [
            math.sqrt((cell[0] - center[0])**2 + (cell[1] - center[1])**2)
            for cell in high_threat_cells
        ]
        
        # Average distance plus margin
        return (sum(distances) / len(distances)) + 2

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))
        self.defense_manager = DefenseManager(28, 28)
        self.attack_manager = AttackManager()
        # Define multiple funnel openings with corresponding spawn points
        self.funnels = [
            {"opening": [[4, 12], [5, 12]], "spawn": [10, 0]},
            {"opening": [[13, 12], [14, 12]], "spawn": [5, 0]},
            {"opening": [[20, 12], [21, 12]], "spawn": [18, 0]}
        ]
        self.current_funnel_index = 0
        self.last_funnel_change = -1
        self.funnel = [[20,12], [21,12]]

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0
        # This is a good place to do initial setup
        self.scored_on_locations = []

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.

        # Update our defense manager with new attack locations
        self.defense_manager.update_threat(self.scored_on_locations)
        # Clear the scored_on_locations for next turn
        self.scored_on_locations = []
        
        self.starter_strategy(game_state)

        game_state.submit_turn()

    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """
        # First, place basic defenses
        self.build_defences(game_state)
        # Now build reactive defenses based on where the enemy scored
        self.build_reactive_defense(game_state)
        # Use our new attack manager to execute attacks
        attack_executed = self.attack_manager.execute_attack(game_state)

    def build_defences(self, game_state):
        """
        Build defenses using our threat-based approach combined with some hardcoded locations.
        """
        row = 12
        # Build a turret line on the front with a gap of 3 filled with walls
        x = 2
        while x <= 26:
            game_state.attempt_spawn(TURRET, [x, row])
            x += 4
        # Fill in the gaps with walls
        game_state.attempt_spawn(WALL, [[0, 13], [27, 13]])  
        new_turrets = [[25, 11], [24,10]]
        game_state.attempt_spawn(TURRET, new_turrets)
        game_state.attempt_upgrade(new_turrets)
        # Lastly, if we have spare SP, let's build some supports
        support_locations = [[4, 9], [5, 9], [6, 9], [7, 9]]
        game_state.attempt_spawn(SUPPORT, support_locations)
        x = 1
        while x <= 26:
            if x == 22:
                x = x + 3
            game_state.attempt_spawn(WALL, [x, row])
            x += 1

        ## Upgrade the turret line
        x = 2
        while x <= 26:
            game_state.attempt_upgrade([x, row])
            x += 4
        
        game_state.attempt_upgrade([[0, 13], [27, 13]])
        
        # Upgrade the supports
        game_state.attempt_upgrade(support_locations)

    def build_reactive_defense(self, game_state):
        """
        This function builds reactive defenses based on where the enemy scored on us from.
        We can track where the opponent scored by looking at events in action frames 
        as shown in the on_action_frame function
        """
        for location in self.scored_on_locations:
            # Build turret one space above so that it doesn't block our own edge spawn locations
            build_location = [location[0], location[1]+1]
            game_state.attempt_spawn(TURRET, build_location)

    def stall_with_interceptors(self, game_state):
        """
        Send out interceptors at random locations to defend our base from enemy moving units.
        """
        # We can spawn moving units on our edges so a list of all our edge locations
        friendly_edges = game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)
        
        # Remove locations that are blocked by our own structures 
        # since we can't deploy units there.
        deploy_locations = self.filter_blocked_locations(friendly_edges, game_state)
        
        # While we have remaining MP to spend lets send out interceptors randomly.
        while game_state.get_resource(MP) >= game_state.type_cost(INTERCEPTOR)[MP] and len(deploy_locations) > 0:
            # Choose a random deploy location.
            deploy_index = random.randint(0, len(deploy_locations) - 1)
            deploy_location = deploy_locations[deploy_index]
            
            game_state.attempt_spawn(INTERCEPTOR, deploy_location)
            """
            We don't have to remove the location since multiple mobile 
            units can occupy the same space.
            """

    def demolisher_line_strategy(self, game_state):
        """
        Build a line of the cheapest stationary unit so our demolisher can attack from long range.
        """
        # First let's figure out the cheapest unit
        # We could just check the game rules, but this demonstrates how to use the GameUnit class
        stationary_units = [WALL, TURRET, SUPPORT]
        cheapest_unit = WALL
        for unit in stationary_units:
            unit_class = gamelib.GameUnit(unit, game_state.config)
            if unit_class.cost[game_state.MP] < gamelib.GameUnit(cheapest_unit, game_state.config).cost[game_state.MP]:
                cheapest_unit = unit

        # Now let's build out a line of stationary units. This will prevent our demolisher from running into the enemy base.
        # Instead they will stay at the perfect distance to attack the front two rows of the enemy base.
        for x in range(27, 5, -1):
            game_state.attempt_spawn(cheapest_unit, [x, 11])

        # Now spawn demolishers next to the line
        # By asking attempt_spawn to spawn 1000 units, it will essentially spawn as many as we have resources for
        game_state.attempt_spawn(DEMOLISHER, [24, 10], 1000)

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy turrets that can attack each location and multiply by turret damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET, game_state.config).damage_i
            damages.append(damage)
        
        # Now just return the location that takes the least damage
        return location_options[damages.index(min(damages))]

    def detect_enemy_unit(self, game_state, unit_type=None, valid_x = None, valid_y = None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units
        
    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                gamelib.debug_write("All locations: {}".format(self.scored_on_locations))


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
