import gamelib
import random
import math
import warnings
from sys import maxsize
import json
import copy

class AttackManager:
    def __init__(self):
        self.last_attack_turn = 0
        self.last_interceptor_turn = 0
        self.consecutive_interceptor_uses = 0
        self.previous_enemy_units = {"walls": [], "turrets": [], "supports": []}
        self.previous_enemy_resources = {"MP": 5, "SP": 40,"health":30}
        self.previous_my_resources={"MP":5 , "SP":40,"health":30 }
        # Add end-of-turn SP tracking
        self.enemy_end_turn_sp = 40  # Default starting SP
        
        # Add turn tracking to avoid redundant processing
        self.last_processed_turn = -1

    def track_enemy_defense_changes(self, game_state):
        # Get current enemy defenses
        enemy_defenses = self.enemy_stationary_units(game_state)

        # Count total defenses
        total_walls = len(enemy_defenses["walls"])
        total_turrets = len(enemy_defenses["turrets"])
        total_supports = len(enemy_defenses["supports"])
        total_defenses = total_walls + total_turrets + total_supports
        
        # Count pending removals
        removed_walls = sum(1 for wall in enemy_defenses["walls"] if wall.pending_removal)
        removed_turrets = sum(1 for turret in enemy_defenses["turrets"] if turret.pending_removal)
        removed_supports = sum(1 for support in enemy_defenses["supports"] if support.pending_removal)
        total_removed = removed_walls + removed_turrets + removed_supports
        
        gamelib.debug_write("\nEnemy defenses - Total: {}, Removed: {}".format(total_defenses, total_removed))
        gamelib.debug_write("\nWalls: {}/{}, Turrets: {}/{}, Supports: {}/{}".format(
            removed_walls, total_walls,
            removed_turrets, total_turrets,
            removed_supports, total_supports
        ))
        
        return {
            "total": total_defenses,
            "removed": total_removed,
            "walls": {"total": total_walls, "removed": removed_walls},
            "turrets": {"total": total_turrets, "removed": removed_turrets},
            "supports": {"total": total_supports, "removed": removed_supports}
        }

    def enemy_stationary_units(self, game_state):
            walls=[]
            turrets=[]
            supports=[]
            for y in range(14,28): #enemy half y coordinates
                for x in range(y-14,42-y):
                    if(game_state.game_map[x,y]):
                        unit = game_state.game_map[x,y][0]
                        if(unit.unit_type=="FF"):
                            walls.append(unit)
                        elif(unit.unit_type=="DF"):
                            turrets.append(unit)
                        elif(unit.unit_type=="EF"):
                            supports.append(unit)
            all_units={}
            all_units["walls"]=walls
            all_units["turrets"]=turrets
            all_units["supports"]=supports
            return all_units
    
    def calculate_sp_removed(self,all_units):
        #for walls
        walls=all_units["walls"]
        wall_sp_removed=sum([0.75*(2+wall.upgraded)*(wall.health/(50+70*wall.upgraded)) for wall in walls if wall.pending_removal])
        turrets=all_units["turrets"]
        turret_sp_removed=sum([0.75*(3+8*turret.upgraded)*(turret.health/(70+0*turret.upgraded)) for turret in turrets if turret.pending_removal])
        supports=all_units["supports"]
        support_sp_removed=sum([0.75*(4+4*support.upgraded)*(support.health/(20+0*support.upgraded)) for support in supports if support.pending_removal])
        return [wall_sp_removed,turret_sp_removed,support_sp_removed]
    
    def get_supports_attacked_by_scout(self, game_state, location):
        '''
        returns the locations of the support within scout range at given location
        '''
        if not game_state.game_map.in_arena_bounds(location):
            self.warn("Location {} is not in the arena bounds.".format(location))
        supports_attacked = []
        '''
        Get the locations in range of the scout units that are also supports
        '''
        possible_locations = game_state.game_map.get_locations_in_range(location, gamelib.GameUnit(SCOUT, game_state.config).attackRange)
        for point in possible_locations:
            if game_state.game_map[point][0].unit_type == SUPPORT:
                supports_attacked.append(point)
        return supports_attacked
    
    def get_supports_boosting_scout(self, game_state, path):
        '''
        Returns the number of scouts that shield the scouts along a given path
        We just want the number of supports in the range of the scout path 
        '''
        supports_on_map = []
        for y in range(14,28): #enemy half y coordinates
                for x in range(y-14,42-y):
                    if(game_state.game_map[x,y]):
                        unit = game_state.game_map[x,y][0]
                        if(unit.unit_type=="EF"):
                            supports_on_map.append(unit)
        supports_boosting = set()
        for path_location in path:
            for support in supports_on_map:
                if game_state.game_map.distance_between_locations(path_location, support.location) <= support.shieldRange:
                    supports_boosting.add(support)
        boost=0
        for support in supports_boosting:
            boost += support.shieldPerUnit
        return boost


    def scout_attack_scorer(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        Returns a weighted sum of the damage it incurs and the damage it causes. We want it to  cause maximum 
        damage and incur minimum possible damage
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            # Get number of supports helping the scouts over the path and add the boost we get from them
            damage_incurred = -self.get_supports_boosting_scout(game_state, path)
            damage_to_supports = 0
            for path_location in path:
                # Get number of enemy turrets that can attack each location and multiply by turret damage
                damage_incurred += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET, game_state.config).damage_i
                # Get number of enemy supports that are attacked at each location and multiply by scout damage
                damage_to_supports += len(self.get_supports_attacked_by_scout(game_state,path_location)) * gamelib.GameUnit(SCOUT, game_state.config).damage_i
            damages.append(damage_to_supports - damage_incurred)

        # Now just return the location that takes the least damage and gives maximum damage to support
        return location_options[damages.index(min(damages))]

    
    def execute_attack(self, game_state):
    # Get enemy units and calculate threat
        enemy_defenses = self.enemy_stationary_units(game_state)
        enemy_MP = game_state.get_resources(1)[1]
        enemy_SP = game_state.get_resources(1)[0]
        my_MP = game_state.get_resources(0)[1]
        my_SP=game_state.get_resources(0)[0]
        my_health=game_state.my_health
        interceptor_spawn_location=[21,7]
        
        # Calculate SP from last turn
        prev_turn_end_enemy_SP = self.enemy_end_turn_sp
        # Each turn players gain 5 SP
        sp_gained_from_removal = max(0, enemy_SP - prev_turn_end_enemy_SP - 5)
        
        gamelib.debug_write(f"Enemy SP at end of last turn: {prev_turn_end_enemy_SP}")
        gamelib.debug_write(f"Current enemy SP: {enemy_SP}")
        gamelib.debug_write(f"SP gained from removal: {sp_gained_from_removal}")

        # Calculate interceptor probability
        turns_since_interceptor = game_state.turn_number - self.last_interceptor_turn

        cooldown_factor = 1.0 if turns_since_interceptor > 1 else [1.0, 0.6, 0.4][min(self.consecutive_interceptor_uses, 2)]

        self.consecutive_interceptor_uses = 0 if turns_since_interceptor > 1 else self.consecutive_interceptor_uses

        enemy_sp_gained_due_to_attack=self.previous_my_resources["health"]-my_health
        # Calculate threat score
        current_enemy_supports = sum([(1 + unit.upgraded) for unit in enemy_defenses["supports"] ])
        prev_enemy_supports=sum([(1 + unit.upgraded) for unit in self.previous_enemy_units["supports"] ])
        future_supports = ((sp_gained_from_removal-enemy_sp_gained_due_to_attack)//4)**(1.7)
        
        w1, w2 = 1.4, 3
        normalizing_factor = 35 * (max(int(game_state.turn_number) - 5, 1)) ** 0.1
        threat_score = ((w1 * enemy_MP) ** (((current_enemy_supports + future_supports) ** 0.8) / w2 + 0.1)) / normalizing_factor
        
        # Determine attack strategy
        interception_probability = threat_score * cooldown_factor
        num_interceptors = (1 if  interception_probability >=1/2 else 0) + (1 if interception_probability >=0.8 else 0)
        
        min_scouts = 10 if game_state.enemy_health <= 5 else 13

        interceptor_threshold = 5     #min enemy mp to send interceptor
        if enemy_MP >= interceptor_threshold and game_state.turn_number >=3 and my_MP<min_scouts and num_interceptors>=1 and current_enemy_supports>=prev_enemy_supports:
            if(num_interceptors==2 and enemy_MP>=12):
                game_state.attempt_spawn(INTERCEPTOR, [5,8], 1)
            game_state.attempt_spawn(INTERCEPTOR, interceptor_spawn_location, 1)

            self.last_interceptor_turn = game_state.turn_number
            self.consecutive_interceptor_uses += 1
        
        if my_MP >= min_scouts:
            game_state.attempt_spawn(SCOUT, [4, 9], math.floor(my_MP))
            self.last_attack_turn = game_state.turn_number
            
        gamelib.debug_write(f"PREVIOUS enemy units: Walls: {len(self.previous_enemy_units['walls'])}, Turrets: {len(self.previous_enemy_units['turrets'])}, Supports: {len(self.previous_enemy_units['supports'])}")
        gamelib.debug_write(f"CURRENT enemy units: Walls: {len(enemy_defenses['walls'])}, Turrets: {len(enemy_defenses['turrets'])}, Supports: {len(enemy_defenses['supports'])}")
        gamelib.debug_write(f"prev_enemy_supports: {prev_enemy_supports}, current_enemy_supports: {current_enemy_supports}")

        # Store only resources for next turn (not enemy units - those will be updated in on_action_frame)
        self.previous_my_resources={"MP":my_MP , "SP":my_SP,"health":my_health }

        return True

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))
        self.attack_manager = AttackManager()
        self.funnel = [[22,12]]
        self.support_index = 0
        self.turrets_index = 0
        self.edge_wall_index = 0
        self.turret_index = 3
        self.turrets_list = [3, 6, 9, 12, 18, 21, 24]

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
        # Clear the scored_on_locations for next turn
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
        # Use our new attack manager to execute attacks
        attack_executed = self.attack_manager.execute_attack(game_state)

    def build_defences(self, game_state):
        """
        Build defenses using our threat-based approach combined with some hardcoded locations.
        """
        # Y coordinate of the defense line
        y = 12
        # Above turret walls
        turrets_walls = [[3, 13], [6, 13]]
        # First deployable turrets
        base_turrets = [[18, 12], [21, 12]]
        game_state.attempt_spawn(TURRET, base_turrets)
        # Build turrets on the front
        for x in range(3, 27, 3):
            game_state.attempt_spawn(TURRET, [x, y])

        # Wall locations 
        wall_locations = [[0, 13], [27, 13]]
        game_state.attempt_spawn(WALL, wall_locations[self.edge_wall_index])   
        self.edge_wall_index = (self.edge_wall_index + 1) % 2

        # Upgrade and deploy supports one at a time
        # Support locations 
        support_locations = [[3, 11], [6, 11], [9, 11], [12, 11]]
        game_state.attempt_spawn(SUPPORT, support_locations[self.support_index])
        if game_state.turn_number > 3 and game_state.get_resources(0)[0] >= 10:
            game_state.attempt_upgrade(support_locations[self.support_index])
        self.support_index = (self.support_index + 1) % 4
        # attack_bool = self.attack_manager.track_enemy_defense_changes(game_state)["turrets"]["total"] < 5 and game_state.turn_number != 0
        # if game_state.turn_number < 3 and attack_bool:
        #     game_state.attempt_spawn(SCOUT, [3, 10], math.floor(game_state.get_resources(0)[1]))

        i = 1 
        j = 26
        while i <= j:
            if [i, y] in self.funnel or i % 3 == 0:
                i += 1
                continue
            if [j, y] in self.funnel or j % 3 == 0:
                j -= 1
                continue 
            game_state.attempt_spawn(WALL, [i, y])
            game_state.attempt_spawn(WALL, [j, y])
            i += 1
            j -= 1
        
        # Check turrets health and remove if less than 30
        for x in range(3, 27, 3):
            if(game_state.game_map[x,y]):
                unit = game_state.game_map[x,y][0]
                if unit.unit_type == "DF" and unit.health < 26:
                    if game_state.turn_number > 2:
                        game_state.attempt_remove([x, y])
                    else :
                        game_state.attempt_spawn(WALL, [x, y+1])

        # # Build walls from left to right
        # if game_state.turn_number < 2:
        #     for x in range(1, 27):
        #         if [x, y] in self.funnel:
        #             continue
        #         game_state.attempt_spawn(WALL, [x, y])

        # Wall locations 
        wall_locations = [[0, 13], [27, 13]]
        game_state.attempt_spawn(WALL, wall_locations[self.edge_wall_index])   
        self.edge_wall_index = (self.edge_wall_index + 1) % 2

        # Build turrets on the front
        for x in range(3, 27, 3):
            game_state.attempt_spawn(TURRET, [x, y])
        
        # Upgrade turret walls
        game_state.attempt_upgrade(turrets_walls[self.turrets_index])
        self.turrets_index = (self.turrets_index + 1) % 2
        # Build a turret line on the front with walls in between
        Current_Sp = game_state.get_resources(0)[0] + 5
        if game_state.turn_number >= 2:
            for x in range(3, 27, 3):
                if(game_state.game_map[x,y]):
                    unit = game_state.game_map[x,y][0]
                    if unit.unit_type == "DF":
                        continue
                if Current_Sp >= 3:
                    game_state.attempt_remove([x, y])
                    Current_Sp -= 3
                               
        # Build walls from right to left and not on funnel locations        
        if game_state.turn_number >= 3:
            for x in range(26, -1, -1):
                if [x, y] in self.funnel or x % 3 == 0:
                    continue
                game_state.attempt_spawn(WALL, [x, y])  
        
        game_state.attempt_spawn(TURRET, [23, 11])
        # Build walls in front of turrets
        game_state.attempt_spawn(WALL, turrets_walls)
        
        # Support locations 
        support_locations = [[2, 11], [3, 11], [4, 11], [3, 10]]
        # for i in range(4):
        #     game_state.attempt_upgrade(support_locations[i])
        #     game_state.attempt_spawn(SUPPORT, support_locations[i])

        # Upgrade and deploy supports one at a time
        game_state.attempt_spawn(SUPPORT, support_locations[self.support_index])
        game_state.attempt_upgrade(support_locations[self.support_index])
        self.support_index = (self.support_index + 1) % 4

        # Upgrade defenses and Advancing the defense line
        if game_state.turn_number > 4:
            new_turrets = [[18,10], [13,9]]
            game_state.attempt_spawn(TURRET, new_turrets)
            # Upgrade Turrets
            game_state.attempt_upgrade([23, 11])
            for x in range(3, 27, 3):
                game_state.attempt_upgrade([x, y])
        
        # Remove walls to get SP and build turrets
        # Current_Sp = game_state.get_resources(0)[0] + 5
        # if game_state.turn_number >= 2:
        #     for x in range(3, 27, 3):
        #         if(game_state.game_map[x,y]):
        #             unit = game_state.game_map[x,y][0]
        #             if unit.unit_type == "DF":
        #                 continue
        #         if Current_Sp >= 3:
        #             game_state.attempt_remove([x, y])
        #             Current_Sp -= 3        
        if(game_state.game_map[self.turrets_list[self.turret_index],y]):
            unit = game_state.game_map[self.turrets_list[self.turret_index],y][0]
            if unit.unit_type == "DF" :
                game_state.attempt_upgrade([self.turrets_list[self.turret_index], y])       
                self.turret_index = (self.turret_index + 6) % 7  

        # # Build walls from right to left and not on funnel locations        
        # if game_state.turn_number >= 3:
        #     for x in range(26, -1, -1):
        #         if [x, y] in self.funnel or x % 3 == 0:
        #             continue
        #         game_state.attempt_spawn(WALL, [x, y])  
        
        game_state.attempt_spawn(TURRET, [22, 10])
        
        # Upgrade defenses and Advancing the defense line
        if game_state.turn_number > 4:
            game_state.number_affordable(WALL) > 2
            for x in range(21, 15, -1):
                if not(game_state.get_resources(0)[0] <= 4):
                    game_state.attempt_spawn(WALL, [x, 10])
                else:
                    break
    def on_action_frame(self, turn_string):
        state = json.loads(turn_string)
        
        # Get current turn number
        current_turn = state["turnInfo"][1] if "turnInfo" in state else -1
        
        # Only process p2Stats once per turn - this effectively identifies the last frame
        if "p2Stats" in state and current_turn != self.attack_manager.last_processed_turn:
            p2_stats = state["p2Stats"]
            self.attack_manager.enemy_end_turn_sp = p2_stats[1]  # SP at index 1
            gamelib.debug_write(f"p2Stats {p2_stats}")
            
            # Create a game state from the current state to get end-of-turn data
            game_state = gamelib.GameState(self.config, json.dumps(state))
            
            # Call enemy_stationary_units to get the enemy units at the end of turn
            end_turn_enemy_units = self.attack_manager.enemy_stationary_units(game_state)
            
            # Update previous_enemy_units with end-of-turn state
            self.attack_manager.previous_enemy_units = copy.deepcopy(end_turn_enemy_units)
            
            # Update the last processed turn to avoid redundancy
            self.attack_manager.last_processed_turn = current_turn
            gamelib.debug_write(f"Updated enemy SP to {self.attack_manager.enemy_end_turn_sp} for turn {current_turn}")
            gamelib.debug_write(f"Updated previous_enemy_units with end-of-turn data for turn {current_turn}")

        # Process breaches
        events = state.get("events", {})
        breaches = events.get("breach", [])
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            if not unit_owner_self:
                # Only log each breach once by checking if it's already in the list
                if location not in self.scored_on_locations:
                    gamelib.debug_write("Got scored on at: {}".format(location))
                    self.scored_on_locations.append(location)

if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
