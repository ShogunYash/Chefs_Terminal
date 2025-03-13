import gamelib
import random
import math
import warnings
from sys import maxsize
import json

class AttackManager:
    def __init__(self):
        self.last_attack_turn = -5  # Track when we last attacked
    
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
        wall_sp_removed=sum([0.75*(2+wall.upgraded)*(wall.health/(50+70*wall.upgraded)) for wall in walls])
        turrets=all_units["turrets"]
        turret_sp_removed=sum([0.75*(3+8*turret.upgraded)*(turret.health/(70+0*turret.upgraded)) for turret in turrets])
        supports=all_units["supports"]
        support_sp_removed=sum([0.75*(4+4*support.upgraded)*(support.health/(20+0*support.upgraded)) for support in supports])
        return [wall_sp_removed,turret_sp_removed,support_sp_removed]

    def execute_attack(self, game_state):
        """
        Executes the attack strategy:
        - If we have 13+ MP, send 13 scouts from the best location
        - Otherwise, send a single interceptor as a distraction
        """
        enemy_MP=game_state.get_resources(1)[1]
        my_MP=game_state.get_resources(0)[1]
        scout_spawn_location= [4,9]
        interceptor_spawn_location=[22,8]
        min_scouts=13
        enemy_defenses=self.enemy_stationary_units(game_state)
        w1=0.8
        w2=0.2
        normalizing_factor=25
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
            p=w1*(current_enemy_supports+future_additional_enemy_supports)+w2*enemy_MP
            return p/ normalizing_factor

        interception_probability=calculate_threat_score()
        num=random.random()
        num_interceptors=0
        if num<=interception_probability:
            num_interceptors+=1
        if num <= interception_probability*0.4:
            num_interceptors+=1

        gamelib.debug_write("\n num-",num)
        gamelib.debug_write("\n p-",interception_probability)
        gamelib.debug_write("\n no. of interceptors -",num_interceptors)

        interceptor_threshold = 9     #min enemy mp to send interceptor
        if enemy_MP >= interceptor_threshold and game_state.turn_number >=2 and my_MP<min_scouts:
            game_state.attempt_spawn(INTERCEPTOR, interceptor_spawn_location, num_interceptors)
        if game_state.enemy_health <= 5:
            min_scouts = 10

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
        if game_state.turn_number < 2 :
            x = 1
            while x <= 26 :
                if [x,y] in self.funnel :
                    x += 1
                    continue
                game_state.attempt_spawn(WALL, [x, y])
                x += 1
        # Build walls from right to left and not on funnel locations        
        if game_state.turn_number > 3 :
            x = 26
            while x >= 1 :
                if [x,y] in self.funnel or x % 3 == 0:
                    x -= 1
                    continue
                game_state.attempt_spawn(WALL, [x, y])
                x -= 1
        # Build a turret line on the front with walls in between
        if game_state.turn_number == 2 :
            # Remove walls where turret need to be deployed
            x = 3
            while x <= 26 :
                if x == 15 or x == 18 :
                    x += 3
                    continue
                game_state.attempt_remove([x,y])
                x += 3
        x = 3
        while x <= 26 :
            game_state.attempt_upgrade(turrets_walls)
            game_state.attempt_spawn(TURRET, [x, y])
            x += 3
        # Build walls in front of turrets
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
        
if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()