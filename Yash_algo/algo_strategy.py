import gamelib
import random
import math
import warnings
from sys import maxsize
import json

class AttackManager:
    def __init__(self):
        self.last_attack_turn = -5  # Track when we last attacked
    
    def execute_attack(self, game_state):
        """
        Executes the attack strategy:
        - If we have 13+ MP, send 7 scouts from the best location
        - Otherwise, send a single interceptor as a distraction
        """
        enemy_MP=game_state.get_resources(1)[1]
        my_MP=game_state.get_resources(0)[1]
        scout_spawn_location= [4,9]
        interceptor_spawn_location=[22,8]
        min_scouts=13

        interceptor_threshold = 13     #min enemy mp to send interceptor
        if enemy_MP >= interceptor_threshold and 7>= game_state.turn_number >=4 and my_MP<=min_scouts:
            game_state.attempt_spawn(INTERCEPTOR, interceptor_spawn_location, 1)
        if enemy_MP <= 5:
            min_scouts = 10

        # Launch many scouts at once for a coordinated attack is min_scouts

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
        # Wall locations 
        wall_locations = [[0, 13], [27, 13]]
        game_state.attempt_spawn(WALL, wall_locations)
        # Above turret walls
        turrets_walls = [[3,13],[6,13]]
        # First deployable turrets
        base_turrets = [[15,12],[18,12]]
        game_state.attempt_spawn(TURRET, base_turrets)
        # Build walls from left to right
        x = 1
        if game_state.turn_number < 2 or game_state.turn_number > 4 :
            while x <= 26 :
                if [x,y] in self.funnel :
                    x += 1
                    continue
                game_state.attempt_spawn(WALL, [x, y])
                x += 1
        # Build a turret line on the front with walls in between
        if game_state.turn_number == 2 :
            # Remove walls where turret need to be deployed
            x = 3
            while x <= 26 :
                game_state.attempt_remove([x,y])
                x += 3
        x = 3
        while x <= 26 :
            game_state.attempt_upgrade(turrets_walls)
            game_state.attempt_spawn(TURRET, [x, y])
            x += 3
        game_state.attempt_spawn(WALL, turrets_walls)
        game_state.attempt_spawn(TURRET, [23,11])
        # Support loactions 
        support_locations = [[2,11],[3,11],[4,11],[3,10]]
        i = 0 
        while i < 4 :
            game_state.attempt_upgrade(support_locations[i])
            game_state.attempt_spawn(SUPPORT, support_locations[i])
            i += 1
        # Upgrade defenses
        if game_state.turn_number > 4 :
            # Upgrade Turrets
            game_state.attempt_upgrade([23,11])
            x = 3
            while x <= 26 :
                game_state.attempt_upgrade([x,y])
                x += 3

    def enemy_stationary_units(self, game_state):
            walls=[]
            turrets=[]
            supports=[]
            for y in range(14,28) #enemy half y coordinates
                for x in range(y-14,42-y)
                    if(game_state.game_map[x,y]):
                        unit = game_state.game_map[x,y][0]
                        if(unit.unit_type=="FF"):
                            walls.append(unit)
                        elif(unit.unit_type=="DF"):
                            turrets.append(unit)
                        elif(unit.unit_type=="EF"):
                            supports.append(unit)
                            
if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()