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
        self.our_prev_health = 30  # Track our health
        self.prev_enemy_MP = False  # Track enemy MP
        self.prev_prev_enemy_MP = False # Track enemy MP
        self.scouts_index = 0  # Track scouts index

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
        scout_spawn_location = [[8,5],[19,5]]
        my_MP = game_state.get_resources(0)[1]
        game_state.attempt_spawn(SCOUT, scout_spawn_location[self.scouts_index], math.floor(my_MP))
        self.scouts_index = (self.scouts_index + 1) % 2

        enemy_MP = game_state.get_resources(1)[1]
        attack_interceptor = False
        min_scouts = 13

        # if game_state.turn_number < 2:
        #     game_state.attempt_spawn(SCOUT, scout_spawn_location, math.floor(my_MP))

        # if game_state.turn_number == 0:
        #     return True
        
        # if game_state.turn_number == 1:
        #     if game_state.my_health < self.our_prev_health:
        #         self.prev_enemy_MP = True
        #     else :
        #         self.prev_enemy_MP = False
        #     self.our_prev_health = game_state.my_health
        #     return True

        # self.prev_prev_enemy_MP = self.prev_enemy_MP
        # if game_state.my_health < self.our_prev_health:
        #         self.prev_enemy_MP = True
        # else :
        #     self.prev_enemy_MP = False
        # self.our_prev_health = game_state.my_health

        # if self.prev_prev_enemy_MP == True and self.prev_enemy_MP == True:
        #     min_scouts = 5
        
        # if my_MP >= min_scouts:
        #     game_state.attempt_spawn(SCOUT, scout_spawn_location[self.scouts_index], math.floor(my_MP))
        #     self.scouts_index = (self.scouts_index + 1) % 2
        # return True

        # # Add this at the beginning of execute_attack
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

        # if my_MP >= min_scouts:
        #     game_state.attempt_spawn(SCOUT, scout_spawn_location, math.floor(my_MP))
        #     self.last_attack_turn = game_state.turn_number
        # return True

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))
        self.attack_manager = AttackManager()
        self.index_one_supp = 0
        self.index_two_supp = 0


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
        pre_support_locations = [[11,6],[12,6],[13,6],[14,6],[15,6]]
        after_support_loactions = [[11,5],[12,5],[13,5],[14,5],[15,5]]
        cover_support_walls = [[10,7],[11,7],[12,7],[13,7],[14,7],[15,7],[16,7]]
        after_cover_support_walls = [[10,5],[16,5]]
        game_state.attempt_spawn(SUPPORT, pre_support_locations)
        game_state.attempt_spawn(WALL, cover_support_walls)
        game_state.attempt_spawn(SUPPORT, after_support_loactions)
        # game_state.attempt_spawn(WALL, after_cover_support_walls)
        game_state.attempt_upgrade(cover_support_walls)
        game_state.attempt_upgrade(pre_support_locations[self.index_one_supp])
        self.index_one_supp = (self.index_one_supp + 1) % 5
        game_state.attempt_upgrade(after_support_loactions[self.index_two_supp])
        self.index_two_supp = (self.index_two_supp + 1) % 5
        # if game_state.turn_number > 2:
        game_state.attempt_upgrade(after_support_loactions)
        game_state.attempt_upgrade(pre_support_locations)
        # game_state.attempt_spawn(SUPPORT, [[]])
            # game_state.attempt_upgrade(after_cover_support_walls)

        # Basic upgraded walls to defend and 4 turrets than all supports
        # first_wall_locations = [[0,13],[1,12],[2,11],[3,10],[4,9],[5,8],[6,8],[7,8],[8,8],[9,8],[10,8],[11,8],[12,8],[13,8],[14,8]]
        # game_state.attempt_spawn(WALL, first_wall_locations)
        # turrets_locations = [[16,8],[19,8]]
        # game_state.attempt_spawn(TURRET, turrets_locations)
        # # Remaining walls
        # remain_wall_locations = [[15,8],[20,8],[21,8],[22,8],[23,9],[24,10],[25,11],[26,12],[27,13]]
        # after_turrets = [[17,5],[13,5]]
        # game_state.attempt_spawn(WALL, after_turrets)
        # support_locations = [[10,3],[11,2],[12,1],[15,1],[16,2],[17,3],[12,2],[15,2]]
        # game_state.attempt_spawn(SUPPORT, support_locations)
        # game_state.attempt_spawn(WALL, remain_wall_locations)

if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
