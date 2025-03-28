import gamelib
import random
import math
import warnings
from sys import maxsize
import json
import copy

# Global variable to store current funnel openings
CURRENT_FUNNEL_OPENINGS = []
BEST_SCOUT_SPAWN_LOCATION = None
BEST_DEFENSE_SCORE = 0
WALL_OPENINGS = []


class AttackManager:
    def __init__(self):
        self.last_attack_turn = 0
        self.last_interceptor_turn = 0
        self.consecutive_interceptor_uses = 0

        self.previous_enemy_units = {"walls": [], "turrets": [], "supports": []}
        self.previous_turn_begin_enemy_resources = {"MP": 5, "SP": 40, "health": 30}
        self.previous_my_resources = {"MP": 5, "SP": 40, "health": 30}
        # Add end-of-turn SP tracking
        self.enemy_end_turn_sp = 40  # Default starting SP

        # Add turn tracking to avoid redundant processing
        self.last_processed_turn = -1
        self.config = None
        
        # Fixed sigmoid parameters
        self.sigmoid_center = 30
        self.sigmoid_steepness = 0.06


    def enemy_stationary_units(self, game_state):
        walls = []
        turrets = []
        supports = []
        for y in range(14, 28):  # enemy half y coordinates
            for x in range(y - 14, 42 - y):
                if game_state.game_map[x, y]:
                    unit = game_state.game_map[x, y][0]
                    if unit.unit_type == "FF":
                        walls.append(unit)
                    elif unit.unit_type == "DF":
                        turrets.append(unit)
                    elif unit.unit_type == "EF":
                        supports.append(unit)
        all_units = {}
        all_units["walls"] = walls
        all_units["turrets"] = turrets
        all_units["supports"] = supports
        return all_units

    def my_stationary_units(self, game_state):
        walls = []
        turrets = []
        supports = []
        for y in range(0, 13):  # my half y coordinates
            for x in range(13 - y, 15 + y):
                if game_state.game_map[x, y]:
                    unit = game_state.game_map[x, y][0]
                    if unit.unit_type == "FF":
                        walls.append(unit)
                    elif unit.unit_type == "DF":
                        turrets.append(unit)
                    elif unit.unit_type == "EF":
                        supports.append(unit)
        all_units = {}
        all_units["walls"] = walls
        all_units["turrets"] = turrets
        all_units["supports"] = supports
        return all_units

    def get_supports_boosting_scout(self, game_state, path):
        """
        Returns the number of scouts that shield the scouts along a given path
        We just want the shileding provided in the range of the scout path
        """
        supports_on_map = []
        for y in range(0, 13):  # my half y coordinates
            for x in range(13 - y, 15 + y):
                if game_state.game_map[x, y]:
                    unit = game_state.game_map[x, y][0]
                    if unit.unit_type == "EF":
                        supports_on_map.append(unit)
        supports_boosting = set()
        for path_location in path:
            for support in supports_on_map:
                if (
                    game_state.game_map.distance_between_locations(
                        path_location, [support.x, support.y]
                    )
                    <= support.shieldRange
                ):
                    supports_boosting.add(support)
        boost = 0
        for support in supports_boosting:
            boost += support.shieldPerUnit + support.shieldBonusPerY * support.y
        return boost

    def check_interceptor_spawn_location(self, game_state):
        start_location = [25, 11]
        path = game_state.find_path_to_edge(start_location)
        path = [location for location in path if location[1] < 16]
        gamelib.debug_write("path", path)
        if len(path) >= 36:
            self.interceptor_spawn_location = [2, 11]

    def sigmoid_decreasing(self, x, center=None, steepness=None):
        """
        A monotonically decreasing sigmoid function with configurable parameters.
        """
        # Use debug parameters if not explicitly provided
        gamelib.debug_write(f"DEBUG: Sigmoid input: {x}, center: {self.sigmoid_center}, steepness: {self.sigmoid_steepness}")
    
        z = self.sigmoid_steepness * (x - self.sigmoid_center)
    
        # Handle extreme values to prevent overflow
        if z > 34:  # exp(34) is near the overflow limit
            return 0
        elif z < -34:  # exp(-34) is effectively 0
            return 1
        else:
            result = 1 / (1 + math.exp(z))
            gamelib.debug_write(f"DEBUG: Sigmoid result: {result}")
            return result

    def update_funnel_openings(self, game_state):
        """
        Analyzes the current game state to identify and update funnel openings.
        This should be called after all defenses are placed for a turn.

        Args:
            game_state: Current game state to analyze
        """
        global CURRENT_FUNNEL_OPENINGS
        CURRENT_FUNNEL_OPENINGS = []
        defense_line_y = 12  # The y-coordinate of your main defensive line

        # Check each position along the defensive line
        for x in range(1, 27):
            # If there's no unit at this position, it's an opening
            if not game_state.contains_stationary_unit([x, defense_line_y]):
                CURRENT_FUNNEL_OPENINGS.append([x, defense_line_y])

        if not game_state.contains_stationary_unit([0, 13]):
            CURRENT_FUNNEL_OPENINGS.append([0, 13])
        if not game_state.contains_stationary_unit([27, 13]):
            CURRENT_FUNNEL_OPENINGS.append([27, 13])

        gamelib.debug_write(f"Updated funnel openings: {CURRENT_FUNNEL_OPENINGS}")

    def update_defense_score(self, game_state, location_options, on_copy=False):
        """
        This function helps us find the safest location to spawn moving units from.
        It analyzes each potential path for damage risk and potential damage to enemy supports.
        Only considers locations where the path exists and damage incurred is below our threshold.
        """
        score_location_pairs = []
        
        # Fixed parameters
       
        w2 = 2 # Damage incurred weight
        damage_threshold_multiplier = 7.5
        w_broken=- 21/(self.enemy_SP)**(0.5)   #weight for breaking enemy units,check if its negative
        
        # Calculate normalization factors
        no_of_scouts = int(math.floor(game_state.get_resources(0)[1]) // 1) + 3.5*on_copy
        # scout_normalising_factor = (no_of_scouts)**(0.5)   #inversely prop to damage incurred weight
        scout_normalising_factor = (((min(10,no_of_scouts+1)/10)**2.7)*no_of_scouts)**(0.8)  #inversely prop to damage incurred weight
    #    *((min(game_state.enemy_health, 7))/7) ** (0.1)
        w2 = w2 / scout_normalising_factor
        # w_broken = w_broken / scout_normalising_factor
        
        w3 = w_broken/5  #brokenF_turret
        w4 = w_broken/6  # damage_given_to_wall
        w5=1.5/((no_of_scouts+1)/9)**4           #for enemy sp
        w6 = ((min(no_of_scouts,6)/6)**(1.1))* no_of_scouts * 0.83      # Support boosting weight

        DAMAGE_THRESHOLD = (no_of_scouts**1.1) * damage_threshold_multiplier
        
        gamelib.debug_write(f"DEBUG: Scout params - w_broken: {w_broken}, w2: {w2}, damage_threshold: {DAMAGE_THRESHOLD}")

        # Evaluate each possible spawn location
        for location in location_options:
            path = game_state.find_path_to_edge(location)

            # Only process locations that have a valid path
            if path:
                support_boost = self.get_supports_boosting_scout(
                    game_state, path
                ) 
                damage_incurred=0
                broken_supports = 0
                broken_turrets = 0
                broken_walls = 0
                path_is_safe = True
                targets_with_og_health=[]
                # Calculate damage along the path
                for path_location in path:
                    # Get number of enemy turrets that can attack and calculate damage
                    damage_incurred += sum(
                        attacker.damage_i
                        for attacker in game_state.get_attackers(path_location, 0)
                    )

                    # Check if damage exceeds our threshold
                    if w2*damage_incurred-w6*support_boost >= DAMAGE_THRESHOLD:
                        path_is_safe = False
                        break
                    # Calculate potential damage to enemy supports
                    x, y = path_location[0], path_location[1]
                    target = game_state.get_target(gamelib.GameUnit(SCOUT, game_state.config, 0, None, x, y))
                    if target:
                        if(target not in {x[0] for x in targets_with_og_health}):
                            original_target_health=target.health
                            targets_with_og_health.append((target,original_target_health ))#append only initially
                        target.health-=2*no_of_scouts
                        if target.unit_type == "EF":
                            if(target.health)<=0:
                                broken_supports+=1
                        elif target.unit_type == "FF":
                            if(target.health)<=0:
                                broken_walls+=1
                        elif target.unit_type == "DF":
                            if(target.health)<=0:
                                broken_turrets+=1
                        
                    
                #replenish all health
                for items in targets_with_og_health:
                    items[0].health=items[1]
                # Only add to our list if the path is safe
                if path_is_safe:
                    defense_score = w_broken * broken_supports + w2 * damage_incurred + w3 * broken_turrets + w4 * broken_walls+ w5*(min(20,max(self.enemy_SP-5,0)))**(1.5)-w6*support_boost
                    score_location_pairs.append((defense_score, location))

        if not on_copy:
            # Update global variables with the best score and location
            global BEST_SCOUT_SPAWN_LOCATION, BEST_DEFENSE_SCORE

            if score_location_pairs:
                # Sort by score (lower is better since we want to minimize damage taken)
                score_location_pairs.sort(key = lambda x: x[0])
                BEST_DEFENSE_SCORE = score_location_pairs[0][0]
                BEST_SCOUT_SPAWN_LOCATION = score_location_pairs[0][1]
                gamelib.debug_write(f"DEBUG: Best defense score: {BEST_DEFENSE_SCORE} and location: {BEST_SCOUT_SPAWN_LOCATION}")
            else:
                # Handle the case where no valid paths are found
                BEST_DEFENSE_SCORE = 10000
                BEST_SCOUT_SPAWN_LOCATION = None
                gamelib.debug_write("DEBUG: No valid paths found")

        else:
            score_location_pairs.sort(key = lambda x: x[0])
            if score_location_pairs:
                gamelib.debug_write(f"DEBUG: Best defense score on copy: {score_location_pairs[0][0]} and location: {score_location_pairs[0][1]}")
            return None if not score_location_pairs else score_location_pairs[0]
    
    def nowall_defense_score_checker(self, game_state, walls):
        '''
        For a list of wall coordinates, this fucntion generates a copy of the game map without that wall, then computes the defense score
        If the computed one is lesser than that obtained with the wall then desirable
        Out of the list we return the one with the least defense score
        '''
        min_nowall_defense_score = 100001
       
        any_nowall_data=False

        for wall in walls:
            x,y=wall.x,wall.y
            placeholder = copy.deepcopy(game_state.game_map[x,y])
            game_state.game_map[x,y] = []
            nowall_data = self.update_defense_score(game_state, game_state.game_map.get_edge_locations(2)+game_state.game_map.get_edge_locations(3),on_copy=True)
            if nowall_data:
                any_nowall_data=True
                score,spawn = nowall_data
                if score<min_nowall_defense_score:
                    min_nowall_defense_score=score
                    best_nowall_location=[wall.x,wall.y]
                    best_nowall_spawn_location=spawn
            game_state.game_map[x,y] = copy.deepcopy(placeholder)
        
        if any_nowall_data:
            return [[], [min_nowall_defense_score, best_nowall_location, best_nowall_spawn_location]][min_nowall_defense_score<BEST_DEFENSE_SCORE-50 and min_nowall_defense_score<0 and game_state.my_health>6]
        else:
            return []


    def execute_attack(self, game_state):
        self.enemy_defenses = self.enemy_stationary_units(game_state)
        self.enemy_MP = game_state.get_resources(1)[1]
        self.enemy_SP = game_state.get_resources(1)[0]
        self.my_MP = game_state.get_resources(0)[1]
        self.my_SP = game_state.get_resources(0)[0]
        self.my_health = game_state.my_health
        # Get enemy units and calculate threat
        self.interceptor_spawn_location = (
            [21, 7] if game_state.contains_stationary_unit([19, 12]) else [25, 11]
        )
        if len(game_state.get_attackers((22,12),0))>=2:
            self.interceptor_spawn_location=[19,5] #start from behind if funnel opening is covered with turrets

        # Calculate SP from last turn
        prev_turn_end_enemy_SP = self.enemy_end_turn_sp
        # Each turn players gain 5 SP
        sp_gained_from_removal = max(0, self.enemy_SP - prev_turn_end_enemy_SP - 5)

        # Calculate interceptor probability
        turns_since_interceptor = game_state.turn_number - self.last_interceptor_turn

        cooldown_factor = (
            1.0
            if turns_since_interceptor > 1
            else [1.0, 0.64*(max(1,self.enemy_MP/7)**(1.10)), 0.4*(max(1,self.enemy_MP/7)**(1.10))][min(self.consecutive_interceptor_uses, 2)]
        )

        self.consecutive_interceptor_uses = (
            0 if turns_since_interceptor > 1 else self.consecutive_interceptor_uses
        )

        enemy_sp_gained_due_to_attack = (
            self.previous_my_resources["health"] - self.my_health
        )
        future_supports = (
            max(0, (sp_gained_from_removal - enemy_sp_gained_due_to_attack * 0.8) // 4)
        ) ** (1.2)

        current_enemy_supports = sum(
            [(1 + unit.upgraded) for unit in self.enemy_defenses["supports"]]
        )
        prev_enemy_supports = sum(
            [(1 + unit.upgraded) for unit in self.previous_enemy_units["supports"]]
        )
        current_my_supports = sum(
            (1 + unit.upgraded)
            for unit in self.my_stationary_units(game_state)["supports"]
        )
        # calculate threat score
        w1, w2, w3, w4 = 1.9, 3.5, 2.5, 0.571
        n1, n2, n3 = 19, 0.75, 0.15
        normalizing_factor = (
            n1 * max(1, current_my_supports ** (n2)) * ((self.my_MP) ** (n3)) 
        )  # decrease interceptors as turns increase
        threat_score = (
            (w1
            * ((max(0, self.enemy_MP - 1)) )** (w3))** (((current_enemy_supports + future_supports) ** w4) / w2 + 0.1)
         )/ normalizing_factor

        # Determine attack strategy
        interception_probability = threat_score * cooldown_factor
        global CURRENT_FUNNEL_OPENINGS
        self.update_funnel_openings(game_state)

        for opening in CURRENT_FUNNEL_OPENINGS:
            if opening[0] <= 18 or opening[0] >= 24:
                interception_probability = 0
                break

      
        min_scouts = 10 if game_state.enemy_health <= 5 else 13
        min_scouts -= len(self.my_stationary_units(game_state)["supports"])
        if not (game_state.turn_number >= 3
            and self.my_MP < min_scouts
            and current_enemy_supports >= prev_enemy_supports-2
        ):
            interception_probability = 0

        """SCOUT LOGIC"""
        self.update_defense_score(
            game_state,
            game_state.game_map.get_edge_locations(2)
            + game_state.game_map.get_edge_locations(3),
        )

        global BEST_SCOUT_SPAWN_LOCATION, BEST_DEFENSE_SCORE, WALL_OPENINGS
        best_spawn_location = BEST_SCOUT_SPAWN_LOCATION
        best_defense_score = BEST_DEFENSE_SCORE
        for openings in WALL_OPENINGS:
            if(opening not in game_state.find_path_to_edge(best_spawn_location)):
                game_state.attempt_spawn(WALL,opening)
        
        
        # Use the simplified sigmoid function
        scout_sending_factor = self.sigmoid_decreasing(best_defense_score)
        gamelib.debug_write(f"DEBUG: Scout factor: {scout_sending_factor}, defense_score: {best_defense_score}")


        # deciding between scout vs interceptor
        if (
            scout_sending_factor < 1 / 2
            and interception_probability < 1 / 2
        ):
            pass  # do nothing
        elif scout_sending_factor >= interception_probability and self.my_MP >= 5:
            game_state.attempt_spawn(SCOUT, best_spawn_location, (int(self.my_MP // 1)))
            self.last_attack_turn = game_state.turn_number
        elif interception_probability >= 1 / 2:
            self.check_interceptor_spawn_location(game_state)
            game_state.attempt_spawn(INTERCEPTOR, self.interceptor_spawn_location, 1)
            self.last_interceptor_turn = game_state.turn_number
            self.consecutive_interceptor_uses += 1

        # Store only resources for next turn (not enemy units - those will be updated in on_action_frame)
        self.previous_my_resources = {
            "MP": self.my_MP,
            "SP": self.my_SP,
            "health": self.my_health,
        }

        # Check if we can remove a wall to improve the defense_score
        walls = self.my_stationary_units(game_state)['walls']
        walls = [unit for unit in walls if (unit.x<=13 and [unit.x,unit.y]!=[1,12]) or unit.x>=25]

        new = self.nowall_defense_score_checker(game_state, walls)
        if new:
            new_defense_score, nowall_location, new_spawn_location = new
            # global BEST_SCOUT_SPAWN_LOCATION, BEST_DEFENSE_SCORE, WALL_OPENINGS
            BEST_DEFENSE_SCORE = new_defense_score
            BEST_SCOUT_SPAWN_LOCATION = new_spawn_location
            game_state.attempt_remove(nowall_location)
            WALL_OPENINGS.append(nowall_location)

        return True



class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write("Random seed: {}".format(seed))
        self.attack_manager = AttackManager()
        self.funnel = [[22, 12]]
        self.support_index = 0
        self.turrets_index = 0
        self.edge_wall_index = 0
        self.turret_index = 3
        self.turrets_list = [3, 6, 9, 12, 18, 21, 24]
        # Initialize empty funnel openings list
        global CURRENT_FUNNEL_OPENINGS
        CURRENT_FUNNEL_OPENINGS = []

    def on_game_start(self, config):
        """
        Read in config and perform any initial setup here
        """
        gamelib.debug_write("Configuring your custom algo strategy...")
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
        self.last_support_turn = 0


    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write(
            "Performing turn {} of your custom algo strategy".format(
                game_state.turn_number
            )
        )
        game_state.suppress_warnings(
            True
        )  # Comment or remove this line to enable warnings.
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
        self.build_defences(game_state)



    def build_defences(self, game_state):
        """
        Build defenses using our threat-based approach combined with some hardcoded locations.
        """

        # Y coordinate of the defense line
        y = 12
        # Build turrets on the front
        for x in range(5, 24, 3):
            game_state.attempt_spawn(TURRET, [x, y])

        # crucial Wall locations
        wall_locations = [
            [0, 13],
            [27, 13],
            [1, 12],
            [2, 12],
            [3, 12],
            [4, 12],
            [24, 12],
            [25, 12],
            [26, 12],
        ]
        support_walls = []
        sp_needed_to_replace_removed = 0
        sp_needed_to_close_wall=0
        #keep this as reserved sp
        global WALL_OPENINGS
        if(WALL_OPENINGS):
            sp_needed_to_replace_removed+=2
        for wall_location in wall_locations:
            if(wall_location not in WALL_OPENINGS):
                game_state.attempt_spawn(WALL,wall_location) 
            else:
                WALL_OPENINGS.remove(wall_location)
        # 1st support
        support_locations = [[15, 1],[14, 0],[16, 2], [15, 2]]
        if game_state.turn_number == 1:
            game_state.attempt_spawn(SUPPORT, support_locations[self.support_index])
            self.support_index = (self.support_index + 1) % len(support_locations)

        
        for x in range(6, 25):
            if x % 3 != 2 and not (21 <= x <= 22) and [x,y] not in WALL_OPENINGS:
                if game_state.get_resources(0)[
                    0
                ] >= 4 and game_state.contains_stationary_unit(
                    [x - 1, y]
                ):  # see game resources[0][0] is my sp,checking if not dangling from behind
                    game_state.attempt_spawn(WALL, [x, y])
                else:
                    if game_state.contains_stationary_unit(
                        [x + 1, y]
                    ) and game_state.contains_stationary_unit([x - 1, y]):
                        game_state.attempt_spawn(
                            WALL, [x, y]
                        )  # dont create dangling walls
            elif [x,y] in WALL_OPENINGS:
                WALL_OPENINGS.remove([x,y])

        
        # Check walls and turrets health and remove if less than equal to threshold
        for x in range(1, 26):
            if game_state.game_map[x, y] and game_state.turn_number >= 3:
                unit = game_state.game_map[x, y][0]
                if unit.unit_type == "FF" and unit.health <= 28 and not unit.upgraded:
                    if game_state.attempt_upgrade([x, y]):
                        continue
                    elif unit.upgraded and unit.health <= 50:
                        game_state.attempt_remove([x, y])
                        sp_needed_to_replace_removed += 2 * (
                            1 - (0.75) * (unit.health / (50 + 70 * unit.upgraded))
                        )

                elif unit.unit_type == "DF" and unit.health <= 28.5:

                    game_state.attempt_remove([x, y])
                    sp_needed_to_replace_removed += 3 * (
                        1 - (0.75) * (unit.health / 70)
                    )

        # # Add wall for protecting left most turret and if possible upgrade it
        # if(game_state.game_map[5,y] and sp_needed_to_replace_removed<=7):
        #     unit = game_state.game_map[5,y][0]
        #     if unit.unit_type == "DF" :
        #         game_state.attempt_upgrade([5, y+1])
        #         game_state.attempt_spawn(WALL,[5, y+1])

        # upgrade wall protecting leftmost supports
        # num_of_my_supports=sum((1+unit.upgraded) for unit in self.attack_manager.my_stationary_units(game_state)["supports"])
        # if(sp_needed_to_replace_removed<=7 and num_of_my_supports>=1):
        #     if(game_state.game_map[3,y]):
        #         unit =game_state.game_map[3,y][0]
        #         if unit.unit_type == "FF" :
        #             game_state.attempt_upgrade([3,y])
        # if(sp_needed_to_replace_removed<=7 and num_of_my_supports>=3):
        #     if(game_state.game_map[4,y]):
        #         unit =game_state.game_map[4,y][0]
        #         if unit.unit_type == "FF" :
        #             game_state.attempt_upgrade([4,y])

        # Build turrets on the back
        (
            game_state.attempt_spawn(TURRET, [22, 10])
            if sp_needed_to_replace_removed<=7 and game_state.get_resources(0)[0]>= 3+sp_needed_to_close_wall
            else None
        )

        # support spawning algo
        # Upgrade and deploy supports one at a time

        if (
            game_state.turn_number > 3
            and game_state.turn_number - self.last_support_turn > 1
            and sp_needed_to_replace_removed<=7 and game_state.get_resources(0)[0]>=4+ sp_needed_to_close_wall     ):  
            for location in support_locations:
                if game_state.game_map[location[0],location[1]]:
                    unit = game_state.game_map[location[0],location[1]][0]
                    if(unit.health>=9 and game_state.get_resources(0)[0]>=4+  sp_needed_to_close_wall):
                        game_state.attempt_upgrade((location[0],location[1]))
            
            if game_state.attempt_spawn(SUPPORT, support_locations[self.support_index]):
                self.support_index = (self.support_index + 1) % len(support_locations)

        my_supports= self.attack_manager.my_stationary_units(game_state)['supports']
        if(sum(1+unit.upgraded for unit in my_supports)>=2 and sp_needed_to_replace_removed<=6 and game_state.get_resources(0)[0]>=2+sp_needed_to_close_wall):
            if(game_state.attempt_spawn(WALL,[15,3] ) and game_state.get_resources(0)[0]>=1+sp_needed_to_close_wall) and game_state.game_map[15,3][0].health<30 :
                game_state.attempt_upgrade([15,3])
        
        # Attempt create walls to protect upgraded turrets
        for x in range(20, 11, -6):
            if game_state.game_map[x, y] and sp_needed_to_replace_removed<=5 and game_state.get_resources(0)[0]>=2+ sp_needed_to_close_wall:
                unit = game_state.game_map[x, y][0]
                if (
                    unit.unit_type == "DF"
                    and unit.health >= 40
                    and game_state.get_resources(0)[0] >= 10
                ):
                    game_state.attempt_upgrade([x, y])
                    game_state.attempt_spawn(WALL, [x, y + 1])

        # First Attempt Upgrade walls protecting turrets
        for x in range(1, 26, 1):
            if (
                game_state.game_map[x, y]
                and game_state.turn_number >= 3
                and sp_needed_to_replace_removed-5 <2 and game_state.get_resources(0)[0]>=1+ sp_needed_to_close_wall
            ):
                game_state.attempt_upgrade([x, y + 1])
        # now try to upgrade some of the normal walls
        # for x in range(4,23,2):
        #     if(game_state.game_map[x,y] and game_state.turn_number>=4 and sp_needed_to_replace_removed<=6):
        #         unit = game_state.game_map[x,y][0]
        #         if unit.unit_type=="FF" and unit.health >=35 :
        #             game_state.attempt_upgrade([x, y])

    def on_action_frame(self, turn_string):
        state = json.loads(turn_string)

        # Get current turn number
        current_turn = state["turnInfo"][1] if "turnInfo" in state else -1

        # Only process p2Stats once per turn - this effectively identifies the last frame
        if (
            "p2Stats" in state
            and current_turn != self.attack_manager.last_processed_turn
        ):
            p2_stats = state["p2Stats"]
            self.attack_manager.enemy_end_turn_sp = p2_stats[1]  # SP at index 1
            gamelib.debug_write(f"p2Stats {p2_stats}")

            # Create a game state from the current state to get end-of-turn data
            game_state = gamelib.GameState(self.config, json.dumps(state))

            # Call enemy_stationary_units to get the enemy units at the end of turn
            end_turn_enemy_units = self.attack_manager.enemy_stationary_units(
                game_state
            )

            # Update previous_enemy_units with end-of-turn state
            self.attack_manager.previous_enemy_units = copy.deepcopy(
                end_turn_enemy_units
            )

            # Update the last processed turn to avoid redundancy
            self.attack_manager.last_processed_turn = current_turn
            gamelib.debug_write(
                f"Updated enemy SP to {self.attack_manager.enemy_end_turn_sp} for turn {current_turn}"
            )
            gamelib.debug_write(
                f"Updated previous_enemy_units with end-of-turn data for turn {current_turn}"
            )
            


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