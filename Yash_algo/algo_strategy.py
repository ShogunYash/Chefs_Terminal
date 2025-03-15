import gamelib
import random
import math
import warnings
from sys import maxsize
import json
import copy

# Global variable to store current funnel openings
CURRENT_FUNNEL_OPENINGS = []
BEST_SCOUT_SPAWN_LOCATION=None
BEST_DEFENSE_SCORE=float(0)

class AttackManager:
    def __init__(self):
        self.last_attack_turn = 0
        self.last_interceptor_turn = 0
        self.consecutive_interceptor_uses = 0
        

        self.previous_enemy_units = {"walls": [], "turrets": [], "supports": []}
        self.previousturn_begin_enemy_resources = {"MP": 5, "SP": 40,"health":30}
        self.previous_my_resources={"MP":5 , "SP":40,"health":30 }
        # Add end-of-turn SP tracking
        self.enemy_end_turn_sp = 40  # Default starting SP
        
        # Add turn tracking to avoid redundant processing
        self.last_processed_turn = -1
        

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
        
    def my_stationary_units(self, game_state):
            walls=[]
            turrets=[]
            supports=[]
            for y in range(0,13): #my half y coordinates
                for x in range(13-y,15+y):
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
            if game_state.game_map[point] and game_state.game_map[point][0].unit_type == SUPPORT:
                supports_attacked.append(point)
        return supports_attacked
    
    def get_supports_boosting_scout(self, game_state, path):
        '''
        Returns the number of scouts that shield the scouts along a given path
        We just want the shileding provided in the range of the scout path 
        '''
        supports_on_map = []
        for y in range(0,13): #my half y coordinates
                for x in range(13-y,15+y):
                    if(game_state.game_map[x,y]):
                        unit = game_state.game_map[x,y][0]
                        if(unit.unit_type=="EF"):
                            supports_on_map.append(unit)
        supports_boosting = set()
        for path_location in path:
            for support in supports_on_map:
                if game_state.game_map.distance_between_locations(path_location, [support.x,support.y]) <= support.shieldRange:
                    supports_boosting.add(support)
        boost=0
        for support in supports_boosting:
            boost += support.shieldPerUnit
        return boost

    def update_defense_score(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        Returns a weighted sum of the damage it incurs and the damage it causes. We want it to  cause maximum 
        damage and incur minimum possible damage
        """
        defense_scores_per_coordinate = []
        w1,w2=-1,1
        safe=True
        DAMAGE_THRESHOLD = 150 # '''CHECK THIS AGAIN'''
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            # Get number of supports helping the scouts over the path and add the boost we get from them
            damage_incurred = 0
            damage_to_supports = 0
            if path: 
                damage_incurred = -self.get_supports_boosting_scout(game_state, path)
                for path_location in path:
                    # Get number of enemy turrets that can attack each location and multiply by turret damage
                    damage_incurred += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET, game_state.config).damage_i
                    if damage_incurred >= DAMAGE_THRESHOLD: safe=False
                    else: safe=True
                    # Get number of enemy supports that are attacked at each location and multiply by scout damage
                    damage_to_supports += len(self.get_supports_attacked_by_scout(game_state,path_location)) * gamelib.GameUnit(SCOUT, game_state.config).damage_i
                defense_scores_per_coordinate.append([float('inf'), w1*damage_to_supports + w2*damage_incurred][safe])
            else: defense_scores_per_coordinate.append(float('inf'))

        # Now just return the  and score that takes the least damage and gives maximum damage to support
        global BEST_SCOUT_SPAWN_LOCATION
        BEST_SCOUT_SPAWN_LOCATION = location_options[defense_scores_per_coordinate.index(min(defense_scores_per_coordinate))]
        global BEST_DEFENSE_SCORE
        BEST_DEFENSE_SCORE = min(defense_scores_per_coordinate)
        return

 
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
        
        if not game_state.contains_stationary_unit([0,13]):
                CURRENT_FUNNEL_OPENINGS.append([0,13])
        if not game_state.contains_stationary_unit([27,13]):
                CURRENT_FUNNEL_OPENINGS.append([27,13])
        
        
        gamelib.debug_write(f"Updated funnel openings: {CURRENT_FUNNEL_OPENINGS}")

    def execute_attack(self, game_state):
        self.enemy_defenses = self.enemy_stationary_units(game_state)
        self.enemy_MP = game_state.get_resources(1)[1]
        self.enemy_SP = game_state.get_resources(1)[0]
        self.my_MP = game_state.get_resources(0)[1]
        self.my_SP=game_state.get_resources(0)[0]
        self.my_health=game_state.my_health
    # Get enemy units and calculate threat
        interceptor_spawn_location=[21,7]
        # Calculate SP from last turn
        prev_turn_end_enemy_SP = self.enemy_end_turn_sp
        # Each turn players gain 5 SP
        sp_gained_from_removal = max(0, self.enemy_SP - prev_turn_end_enemy_SP - 5)
        
        gamelib.debug_write(f"Enemy SP at end of last turn: {prev_turn_end_enemy_SP}")
        gamelib.debug_write(f"Current enemy SP: {self.enemy_SP}")
        gamelib.debug_write(f"SP gained from removal: {sp_gained_from_removal}")

        # Calculate interceptor probability
        turns_since_interceptor = game_state.turn_number - self.last_interceptor_turn

        cooldown_factor = 1.0 if turns_since_interceptor > 1 else [1.0, 0.6, 0.4][min(self.consecutive_interceptor_uses, 2)]

        self.consecutive_interceptor_uses = 0 if turns_since_interceptor > 1 else self.consecutive_interceptor_uses

        enemy_sp_gained_due_to_attack=self.previous_my_resources["health"]-self.my_health
        future_supports = (max(0,(sp_gained_from_removal-enemy_sp_gained_due_to_attack*0.8)//4))**(1.2)

        current_enemy_supports = sum([(1 + unit.upgraded) for unit in self.enemy_defenses["supports"] ])
        prev_enemy_supports=sum([(1 + unit.upgraded) for unit in self.previous_enemy_units["supports"] ])
        #calculate threat score
        w1, w2,w3 = 1.9, 4, 2.3
        normalizing_factor = 17*(max(1,len(self.my_stationary_units(game_state)["supports"]))**(1))*(self.my_MP)**(0.2) #decrease interceptors as turns increase
        threat_score = ((w1 * (self.enemy_MP**(w3))) ** (((current_enemy_supports + future_supports) ** 0.51) / w2 +0.1)) / normalizing_factor
        
        
        # Determine attack strategy
        interception_probability = threat_score * cooldown_factor
        global CURRENT_FUNNEL_OPENINGS
        self.update_funnel_openings(game_state)
        
        for opening in CURRENT_FUNNEL_OPENINGS:
            if(opening[0]<=17 or opening[0]>=24):
                interception_probability=0
                break

        num_interceptors = (1 if  interception_probability >=1/2 else 0) 
        
        min_scouts = 10 if game_state.enemy_health <= 5 else 13
        min_scouts-=len(self.my_stationary_units(game_state)["supports"])


        interceptor_threshold = 5   #min enemy mp to send interceptor
        if (self.enemy_MP >= interceptor_threshold and game_state.turn_number >=2 and self.my_MP<min_scouts and current_enemy_supports>=prev_enemy_supports):
            game_state.attempt_spawn(INTERCEPTOR, interceptor_spawn_location, num_interceptors)
            self.last_interceptor_turn = game_state.turn_number
            self.consecutive_interceptor_uses += 1
        
        '''SCOUT LOGIC'''
        self.update_defense_score(game_state, game_state.game_map.get_edge_locations(2)+game_state.game_map.get_edge_locations(3))
        best_spawn_location = BEST_SCOUT_SPAWN_LOCATION
        best_defense_score = BEST_DEFENSE_SCORE  
        scout_normalising_factor = 10.0
        num_scouts = (int(best_defense_score//scout_normalising_factor))
        # if num_scouts<=4:
        #     num_scouts=0
        game_state.attempt_spawn(SCOUT, best_spawn_location, num_scouts)
        self.last_attack_turn = game_state.turn_number
            
        
        # Store only resources for next turn (not enemy units - those will be updated in on_action_frame)
        self.previous_my_resources={"MP":self.my_MP , "SP":self.my_SP,"health":self.my_health }

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
        # Initialize empty funnel openings list
        global CURRENT_FUNNEL_OPENINGS
        CURRENT_FUNNEL_OPENINGS = []

    

        
        

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
        self.last_support_turn=0

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
        # Build turrets on the front
        for x in range(5, 24, 3):
            game_state.attempt_spawn(TURRET, [x, y])

        # crucial Wall locations 
        wall_locations = [[0, 13], [27, 13],[1,12],[2,12],[3,12],[4,12],[24,12],[25,12],[26,12],]
        game_state.attempt_spawn(WALL, wall_locations)   
        #1st support
        support_locations = [[2, 11],[3,11],[3,10],[4,11]]
        if game_state.turn_number == 1:
            game_state.attempt_spawn(SUPPORT, support_locations[self.support_index])
            self.support_index = (self.support_index + 1) % len(support_locations) 
            
        for x in range(1, 27):
            if x % 3 != 2 and [x, y] and not (21<=x<=22) :
                game_state.attempt_spawn(WALL, [x, y])

        sp_needed_to_replace_removed=0
        # Check walls and turrets health and remove if less than equal to threshold
        for x in range(1,26):
            if(game_state.game_map[x,y] and  game_state.turn_number >= 3):
                unit = game_state.game_map[x,y][0]
                if  (unit.unit_type == "FF" and unit.health <= 28+20*unit.upgraded):
                    if(game_state.attempt_upgrade([x, y])):
                        continue
                    else:  
                        game_state.attempt_remove([x, y])
                        sp_needed_to_replace_removed+=2*(1-(0.75)*(unit.health/(50+70*unit.upgraded)))
                    
                elif (unit.unit_type == "DF" and unit.health <=28.5):

                    game_state.attempt_remove([x, y])
                    sp_needed_to_replace_removed+=3*(1-(0.75)*(unit.health/70))
       
        
        # Add wall for protecting left most turret and if possible upgrade it
        if(game_state.game_map[5,y] and sp_needed_to_replace_removed<=7):
            unit = game_state.game_map[5,y][0]
            if unit.unit_type == "DF" :
                game_state.attempt_upgrade([5, y+1])
                game_state.attempt_spawn(WALL,[5, y+1])
                        
        # Build turrets on the back
        game_state.attempt_spawn(TURRET, [21, 10]) if sp_needed_to_replace_removed<=7 else None

        #support spawning algo
        # Upgrade and deploy supports one at a time
        
        if game_state.turn_number > 3 and game_state.turn_number-self.last_support_turn>1 and sp_needed_to_replace_removed<=6:
            game_state.attempt_upgrade(support_locations)
            if(game_state.attempt_spawn(SUPPORT, support_locations[self.support_index])):
                self.support_index = (self.support_index + 1) % len(support_locations)
            
            
        # Attempt create walls to protect upgraded turrets
        for x in range(5, 27):
            if(game_state.game_map[x,y] and sp_needed_to_replace_removed<=7):
                unit = game_state.game_map[x,y][0]
                if unit.unit_type == "DF" and unit.health >=40 and game_state.get_resources(0)[0] >= 10:
                    game_state.attempt_upgrade([x, y])
                    game_state.attempt_spawn(WALL,[x, y+1])

        
        

        # First Attempt Upgrade walls protecting turrets
        for x in range(1, 26, 1):
            if(game_state.game_map[x,y] and game_state.turn_number>=3 and sp_needed_to_replace_removed<=6):
                game_state.attempt_upgrade([x, y+1])
        #now try to upgrade some of the normal walls            
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
