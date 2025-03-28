import gamelib
import random
import math
import warnings
from sys import maxsize
import json

class AttackManager:
    def __init__(self):
        self.last_attack_turn = 0  # Track when we last attacked
        self.last_interceptor_turn = 0  # Track when we last used interceptors
        self.consecutive_interceptor_uses = 0  # Track consecutive uses

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

    def execute_attack(self, game_state):
        """
        Executes the attack strategy:   
        - If we have 13+ MP, send 13 scouts from the best location
        - Otherwise, send a single interceptor as a distraction
        """

        enemy_MP = game_state.get_resources(1)[1]
        my_MP = game_state.get_resources(0)[1]
        scout_spawn_location = [4, 9]
        attack_interceptor = False
        min_scouts = 13

        # Add this at the beginning of execute_attack
        # defense_stats = self.track_enemy_defense_changes(game_state)

        # if defense_stats["total"] == defense_stats["supports"]["total"] and defense_stats["supports"]["removed"] == 0 and game_state.turn_number > 1:
        #     game_state.attempt_spawn(SCOUT, scout_spawn_location, math.floor(my_MP))
        #     return True
            
        # if defense_stats["removed"] > 4 and defense_stats["supports"]["removed"] == 0 :
        #     attack_interceptor = True
        
        # if attack_interceptor:
        #     game_state.attempt_spawn(INTERCEPTOR, [21, 7], 1)
        #     self.last_interceptor_turn = game_state.turn_number
        #     game_state.attempt_spawn(SCOUT, scout_spawn_location, math.floor(my_MP))
        #     return True

        # else:
        # Calculate time since last interceptor usage
        turns_since_interceptor = game_state.turn_number - self.last_interceptor_turn
        
        if turns_since_interceptor >1:
            self.consecutive_interceptor_uses = 0
            interceptor_cooldown_factor = 1.0  # Full probability
        else:
            # Apply the specific decay pattern: 1 -> 3/5 -> 2/5
            if self.consecutive_interceptor_uses == 0:
                interceptor_cooldown_factor = 1.0
            elif self.consecutive_interceptor_uses == 1:
                interceptor_cooldown_factor = 0.6
            else:
                interceptor_cooldown_factor = 0.4
        
        interceptor_spawn_location = [21, 7]
        enemy_defenses = self.enemy_stationary_units(game_state)
        w1=1.3
        w2=3
        normalizing_factor=50*(max(int(game_state.turn_number)-5 , 1))**(0.2)
        def calculate_threat_score():
            current_enemy_supports=0
            for unit in enemy_defenses["supports"]:
                if not unit.pending_removal:
                    current_enemy_supports+=1+unit.upgraded
                    
            gamelib.debug_write("\n current_enemy_supports-",current_enemy_supports)

            #counts supports in enemy base which are not pending removal
            #now add sp gained from removing turrets and walls(ignore supports as if someone removed support they wouldnt attack next)
            future_additional_enemy_supports=(self.calculate_sp_removed(enemy_defenses)[0]+self.calculate_sp_removed(enemy_defenses)[1])//4
            gamelib.debug_write("\n future_enemy_supports-",future_additional_enemy_supports)
            p = (w1*enemy_MP)**(((current_enemy_supports+future_additional_enemy_supports)**0.9)/w2 + 0.2)
            return min(0.9, p/ normalizing_factor)

        interception_probability = calculate_threat_score() * interceptor_cooldown_factor
        num=random.random()
        num_interceptors=0
        if num<=interception_probability:
            num_interceptors+=1
        if num <= interception_probability*0.4:
            num_interceptors+=1

        gamelib.debug_write("\n num-",num)
        gamelib.debug_write("\n p-",interception_probability)
        gamelib.debug_write("\n no. of interceptors -",num_interceptors)

        if game_state.enemy_health <= 5:
            min_scouts = 10

        interceptor_threshold = 5     #min enemy mp to send interceptor
        if enemy_MP >= interceptor_threshold and game_state.turn_number >=3 and my_MP<min_scouts and num_interceptors>=1:
            if(num_interceptors==2 and enemy_MP>=12):
                game_state.attempt_spawn(INTERCEPTOR, [5,8], 1)
            game_state.attempt_spawn(INTERCEPTOR, interceptor_spawn_location, 1)

            self.last_interceptor_turn = game_state.turn_number
            self.consecutive_interceptor_uses += 1
    
        # Launch many scouts at once for a coordinated attack is min_scouts
        #future note- improve scout sending strategy 

        if my_MP >= min_scouts:
            game_state.attempt_spawn(SCOUT, scout_spawn_location, math.floor(my_MP))
            self.last_attack_turn = game_state.turn_number
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

        # Build turrets on the front
        for x in range(3, 27, 3):
            game_state.attempt_spawn(TURRET, [x, y])

        # Wall locations 
        wall_locations = [[0, 13], [27, 13]]
        game_state.attempt_spawn(WALL, wall_locations[self.edge_wall_index])   
        self.edge_wall_index = (self.edge_wall_index + 1) % 2

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
        # Upgrade and deploy supports one at a time
        # Support locations 
        support_locations = [[3, 11], [6, 11], [9, 11], [12, 10]]
        game_state.attempt_spawn(SUPPORT, support_locations[self.support_index])
        if game_state.turn_number > 3 and game_state.get_resources(0)[0] >= 10:
            game_state.attempt_upgrade(support_locations[self.support_index])
        self.support_index = (self.support_index + 1) % 4
        
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

        # Build turrets on the front
        for x in range(3, 27, 3):
            game_state.attempt_spawn(TURRET, [x, y])
        
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
        # Build walls in front of turrets
        game_state.attempt_spawn(WALL, turrets_walls)
        
        # Upgrade defenses and Advancing the defense line
        if game_state.turn_number > 4:
            game_state.number_affordable(WALL) > 2
            for x in range(21, 15, -1):
                if not(game_state.get_resources(0)[0] <= 4):
                    game_state.attempt_spawn(WALL, [x, 10])
                else:
                    break
            # Upgrade turret walls
            game_state.attempt_upgrade(turrets_walls[self.turrets_index])
            self.turrets_index = (self.turrets_index + 1) % 2


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
