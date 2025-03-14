    def build_defences(self, game_state):
        """
        Build defenses using our threat-based approach combined with some hardcoded locations.
        """

        # Y coordinate of the defense line
        y = 12
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
        attack_bool = self.attack_manager.track_enemy_defense_changes(game_state)["turrets"]["total"] < 5 and game_state.turn_number != 0
        if game_state.turn_number < 3 and attack_bool:
            game_state.attempt_spawn(SCOUT, [3, 10], math.floor(game_state.get_resources(0)[1]))

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
        
        # Upgrade defenses and Advancing the defense line
        if game_state.turn_number > 4:
            game_state.number_affordable(WALL) > 2
            for x in range(21, 15, -1):
                if not(game_state.get_resources(0)[0] <= 4):
                    game_state.attempt_spawn(WALL, [x, 10])
                else:
                    break