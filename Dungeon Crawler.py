import pygame, random, math, queue, os

from dataclasses import dataclass, field
from typing import Any

@dataclass(order=True)
class PrioritizedItem():
    priority: int
    item: Any=field(compare=False)

pygame.init()
clock = pygame.time.Clock()

size = (600, 600)
screen = pygame.display.set_mode(size)

#Constants
rows = 30
columns = 30
tileWidth = 10
scale = 10

#Buttons
mainMenuButtons = ["play", "settings", "exit"]
gameButtons = ["home"]
settingsButtons = ["toggleMusic", "toggleSound", "home"]

#Stores directions
directions = {
    "left" : pygame.math.Vector2(-1, 0),
    "right" : pygame.math.Vector2(1, 0),
    "up" : pygame.math.Vector2(0, -1),
    "down" : pygame.math.Vector2(0, 1)
}

#Stores different fonts in a dictionary
fonts = {
    "large" : pygame.font.SysFont(None, 48),
    "medium" : pygame.font.SysFont(None, 24)
}

#Init
grid = []
rooms = []
entities = []
effects = []
player = None
levelCount = 1
score = 0

#Stores the list of all tile types which entities cannot walk through
collidable = ["wall", "border", "player", "lockedDoor", "enemy"]

#Stores all the different tile types within a list
tileTypesList = ["wall", "border", "floor", "player", "door", "lockedDoor", "enemy"]

#Creates an empty dictionary for tile types
tileTypes = {}
#Iterates through each tileType within tileTypesList
for tileType in tileTypesList:
    #Forms the directory for the image of the tile to be accessed through concatenation
    directory = "tiles/" + tileType + ".png"
    #Loads the image from the directory and scales it to a resolution of tileWidth x tileWidth pixels
    sprite = pygame.transform.scale(pygame.image.load(directory), (tileWidth * scale, tileWidth * scale))
    #Stores the sprite into the dictionary where its key is the name of the tileType
    tileTypes[tileType] = sprite

#Stores the list of all effect names and the number of frames they have
effectTypesList = {
    "hit" : 3,
    "death" : 4
}

#Creates an empty dictionary for effects to be stored within
effectTypes = {}

#Loads all the effects and organises them into a dictionary for later use
for effectType in effectTypesList:
    #Gets the number of frames of a particular type of effect
    numberOfFrames = effectTypesList[effectType]
    #Creates a list within the dictionary for the frames of the effect to be stored
    effectTypes[effectType] = []
    #Concatenates strings to form the directory of the folder which holds the effect frames
    folderDirectory = "effects/" + effectType + "/"
    #Loops through the individual frames within the folder
    for i in range(numberOfFrames):
        #Concatenates strings to form the directory of a frame 
        directory = folderDirectory + str(i) + ".png"
        #Loads the image from the directory as well as scaling the image to a resolution of tileWidth x tileWidth pixels
        sprite = pygame.transform.scale(pygame.image.load(directory), (tileWidth * scale, tileWidth * scale))
        #Stores the loaded sprite into the effectTypes dictionary 
        effectTypes[effectType].append(sprite)

#Stores list of sound names
soundNames = ["hit", "death", "roomComplete", "roomEnter"]

#Creates an empty dictionary for sound effects to be stored within
sounds = {}

#Loads all sound effects into the sounds dictionary
for soundName in soundNames:
    #Forms the directory for the particular sound to be loaded
    directory = "sfx/" + soundName + ".wav"
    #Stores the sound within the dictionary as a PyGame sound object
    sounds[soundName] = pygame.mixer.Sound(directory)

#Loads music
pygame.mixer.music.load("music.mp3")
#Adjusts volume
pygame.mixer.music.set_volume(0.2)
#Plays music infinitely
pygame.mixer.music.play(-1)

musicEnabled = True
soundEnabled = True

class Tile():
    def __init__(self, x, y, tileType):
        self.x = x
        self.y = y
        self.tileType = tileType

    def getSprite(self):
        #Fetches the sprite from the tileTypes dictionary
        return tileTypes[self.tileType]

    #Draws tile
    def draw(self):
        #Stores the result of the player being within bounds
        #as a boolean
        xInBounds = player.x - 3 <= self.x <= player.x + 3
        yInBounds = player.y - 3 <= self.y <= player.y + 3
        #If both conditions are not met, then do not
        #draw the tile
        if not(xInBounds and yInBounds): return
        
        #Calls the getSprite method to fetch the tile's sprite
        sprite = self.getSprite()
        #Gets the offset to position the focus towards the player
        offset = getOffset()
        #Converts the 2D array coordinates to position measured in pixels
        position = (self.x * tileWidth * scale + offset.x, self.y * tileWidth * scale + offset.y)
        #Draws the sprite at specified position
        screen.blit(sprite, position)

    def getNeighbours(self):
        neighbours = []
        for direction in directions.items():
            xNew = int(self.x + direction[1].x)
            yNew = int(self.y + direction[1].y)
            
            xInBounds = 1 <= xNew <= columns - 2
            yInBounds = 1 <= yNew <= rows - 2

            if not (xInBounds and yInBounds): continue
            
            neighbourTile = grid[yNew][xNew]
            neighbours.append(neighbourTile)
            
        return neighbours

    def getCost(self):
        if self.tileType == "floor":
            return 1
        elif self.tileType == "wall":
            return 5
        elif self.tileType == "border":
            return 999

class Effect(Tile):
    def __init__(self, x, y, tileType, frames):
        #Inherits method and attributes from the tile class
        super().__init__(x, y, tileType)

        #Stores the frames that the object will cycle through
        #throughout its lifetime
        self.frames = frames.copy()

        #Stores the lifetime of the effect based on the number of frames
        self.timer = len(self.frames) * 3
        self.initialTimer = self.timer

    def getSprite(self):
        #Get the current frame of the effect relative to how long the effect
        #has been around for
        frame = (self.initialTimer - self.timer) // 3
        #Returns the sprite that has been fetched
        return self.frames[frame]

    def update(self):
        #Decrements the timer
        self.timer -= 1
        #If the timer has reached 0 then remove the effect from the game
        if self.timer <= 0:
            effects.remove(self)
        
#The entity class defines an object which can move around
#the level and attack other entities. It inherits methods
#and attributes from the tile class.
class Entity(Tile):
    #Takes in coordinates and tileType as parameters to be used
    #in the constructor method
    def __init__(self, x, y, tileType):
        #Inherits method and attributes from the tile class
        super().__init__(x, y, tileType)

        #The hitpoints attribute is decreased when the entity
        #attacked by other entities
        self.maxHitpoints = 3
        self.hitpoints = self.maxHitpoints
        #The power attribute determines the damage that
        #this entity can deal to other entities
        self.power = 1

    #Moves the entity in a direction
    def move(self, direction):
        #Sets the x attribute of the entity according to the
        #x component of the direction vector object
        self.x += int(direction.x)
        #Sets the y attribute of the entity according to the
        #y component of the direction vector object
        self.y += int(direction.y)

    def getTargetEntity(self, direction):
        x = self.x + direction.x
        y = self.y + direction.y
        for entity in entities:
            if entity.x == x and entity.y == y:
                return entity

    def willCollide(self, x, y):
        for entity in entities:
            if entity.x == x and entity.y == y and entity != self:
                return True
        return False

    def attack(self, targetEntity):
        #Deducts hitpoints from the target entity
        targetEntity.hitpoints -= self.power
        #Calls the create effect function
        createEffect(targetEntity.x, targetEntity.y, "hit")
        #Plays hit sound
        playSound("hit")
        
#The enemy class defines the enemy object which inherits
#methods and attributes from the entity class
class Enemy(Entity):
    def __init__(self, x, y, tileType, room):
        #Inherits methods and attributes from parent class
        super().__init__(x, y, tileType)
        #Ensures tile type is "enemy"
        self.tileType = "enemy"
        #Stores the room the enemy has spawned 
        self.room = room
        #Cooldown for enemy movement/attacks
        self.actionTimer = 30

        #Set attributes of the enemy according to the level count
        global levelCount
        self.hitpoints = math.ceil(2 + 1 * levelCount)
        self.power = math.ceil(1.3 * levelCount)

    def update(self):
        global score
        
        if self.actionTimer > 0:
            #Decrements the action timer
            self.actionTimer -= 1
        else:
            #Calls the decide action method
            self.decideAction()

        if self.hitpoints <= 0:
            #Create death effect
            createEffect(self.x, self.y, "death")
            #Plays death sound
            playSound("death")
            #Remove all references of enemy
            entities.remove(self)
            self.room.enemies.remove(self)

            #Increase score when the enemy dies
            #Score increase depends on the level count
            score += 200 + 100 * levelCount

    def getDirection(self):
        #Returns a vector based on the player's
        #position from the enemy
        if self.x > player.x:
            return directions["left"]
        elif self.x < player.x:
            return directions["right"]
        elif self.y < player.y:
            return directions["down"]
        elif self.y > player.y:
            return directions["up"]

    def decideAction(self):
        #Resets the action timer
        self.actionTimer = 30
        #Gets direction of the player
        direction = self.getDirection()
        #Gets the target entity
        targetEntity = self.getTargetEntity(direction)
        #Gets the tile at that direction
        nextTile = grid[int(self.y + direction.y)][int(self.x + direction.x)]
        #Checks if the enemy will collide with another entity at that tile's position
        if self.willCollide(nextTile.x, nextTile.y):
            #If it does and the entity it has collided into is a player
            if targetEntity == player:
                #Then call the attack method while passing in the player object
                self.attack(player)
        else:
            #Calls the move method with the direction calculated
            self.move(direction)

def createEffect(x, y, effectType):
    #Creates effect object at the given coordinates
    effect = Effect(x, y, "effect", effectTypes[effectType])
    #Stores the effect in a list as a reference
    effects.append(effect)
        
#The player class defines the player object which inherits
#methods and attributes from the entity class. It also
#defines its own methods and attributes that is
#specific to the player.
class Player(Entity):
    #Takes in coordinates and tileType as parameters to be used
    #in the constructor method
    def __init__(self, x, y, tileType):
        #Inherits method and attributes from the entity class
        super().__init__(x, y, tileType)
        #Sets the tileType attribute to "player" as the player object
        #must have this tileType in order to function and appear
        #correctly
        self.tileType = "player"

        #This attribute is used as a cooldown on moving the player
        self.moveTimer = 20
        self.attackTimer = 20

        #Redefines hitpoints for the player
        self.maxHitpoints = 30
        self.hitpoints = self.maxHitpoints

    #Gets the player's movement-related key presses
    #and executes methods depending on the input
    def getDirection(self):
        direction = None
        #Gets all the keys pressed and executes
        #the move method with the direction associated
        #with it (the direction depends on the particular
        #key pressed)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a]:
            direction = directions["left"]
        if keys[pygame.K_d]:
            direction = directions["right"]
        if keys[pygame.K_w]:
            direction = directions["up"]
        if keys[pygame.K_s]:
            direction = directions["down"]
        return direction

    
    def doAction(self):
        #Decrements the cooldowns 
        if self.moveTimer > 0:
            self.moveTimer -= 1

        if self.attackTimer > 0:
            self.attackTimer -= 1

        #Gets direction based on player input
        direction = self.getDirection()
        if direction:
            #Gets the entity that the player may walk into
            targetEntity = self.getTargetEntity(direction)
            #If the entity does not exist then move towards direction
            if self.moveTimer <= 0 and not targetEntity:
                #moveTimer attribute set to 20 once the
                #player moves
                self.moveTimer = 20
                #Calls move method
                self.move(direction)
            #If the entity does exist then attack entity towards direction
            elif self.attackTimer <= 0 and targetEntity:
                #attackTimer attribute set to 20 once
                #the player attacks
                self.attackTimer = 20
                #Calls the attack method
                self.attack(targetEntity)

    #This move method has been redefined
    #to account for collisions with walls
    #and the movement cooldown
    def move(self, direction):
        self.x += int(direction.x)
        self.y += int(direction.y)

        #Gets the tile from the 2D array
        #at the new position of the player
        nextTile = grid[self.y][self.x]
        #If the tileType of the tile classifies
        #as a colidable tile, then the movement is
        #reversed
        if self.willCollide(nextTile.x, nextTile.y) or nextTile.tileType in collidable:
            self.x -= int(direction.x)
            self.y -= int(direction.y)

    def update(self):
        if self.hitpoints <= 0:
            print("You have been defeated by an enemy.\nGame over.")
            os._exit(0)

        self.doAction()
            
class Room():
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width 
        self.height = height

        self.enemies = []
        self.borders = []
        self.floors = []

        for row in range(self.height):
            for col in range(self.width):
                tile = grid[self.y + row][self.x + col]
                if tile.tileType == "border":
                    self.borders.append(tile)
                elif tile.tileType == "floor":
                    self.floors.append(tile)

        self.door = self.getRandomBorderTile()
        self.active = False
        self.completed = False

    def isRoomOverlapping(self, x, y, width, height):
        for row in range(height + 2):
            for col in range(width + 2):
                xInBounds = self.x - 1 <= x + col <= self.x + self.width + 1
                yInBounds = self.y - 1 <= y + row <= self.y + self.height + 1

                if xInBounds and yInBounds: return True

    def getSpawnTile(self):
        #Calculates coordinates of random tile within the room
        x = self.x + random.randint(1, self.width - 2)
        y = self.y + random.randint(1, self.height - 2)
        while x == player.x and y == player.y:
            x = self.x + random.randint(1, self.width - 2)
            y = self.y + random.randint(1, self.height - 2)            
        #Gets the tile from the coordinates
        tile = grid[y][x]
        #Returns the tile
        return tile

    def completeRoom(self):
        self.active = False
        self.completed = True
        self.door.tileType = "door"

        #Plays complete sound
        playSound("roomComplete")

        #Checks if all rooms are completed
        if areAllRoomsCompleted():
            #Move onto the next level
            newLevel()
            

    def activateRoom(self):
        self.active = True
        self.door.tileType = "lockedDoor"
        self.spawnEnemies()

        #Plays room enter sound
        playSound("roomEnter")

    def spawnEnemies(self):
        global levelCount
        
        for i in range(random.randint(1, 2) + levelCount):        
            #Gets the spawn tile
            spawnTile = self.getSpawnTile()
            #Creates an enemy object
            enemy = Enemy(spawnTile.x, spawnTile.y, "enemy", self)
            #Appends it to the entities list
            entities.append(enemy)
            #Appends it to the room's enemy list
            self.enemies.append(enemy)

    def isContainingPlayer(self):
        xInBounds = self.x + 1 < player.x < self.x + self.width - 2
        yInBounds = self.y + 1 < player.y < self.y + self.height - 2

        return xInBounds and yInBounds

    #Runs every frame
    def update(self):
        #Checks if the room has not been visited and if
        #the player is inside the room
        if self.completed == False and self.isContainingPlayer() and self.active == False:
            #Actives the room (locks the door, spawns enemies)
            self.activateRoom()

        #Checks if the room is currently active and
        #that there are no more enemies remaining
        if self.active == True and len(self.enemies) == 0:
            #Completes the room (unlocks the door)
            self.completeRoom()

        updateElements(self.enemies)

    def getRandomBorderTile(self):
        return random.choice(self.borders)

def playSound(soundName):
    #If sound is disabled then return the function
    if not soundEnabled: return 
    #Accesses a sound object from the sounds dictionary and plays it
    sounds[soundName].play()

def areAllRoomsCompleted():
    #Iterates through each room
    for room in rooms:
        #If a single room is found to be not completed, then return false
        if room.completed == False:
            return False
    #If no rooms left have been not completed, then return true
    return True

def getOffset():
    #Calculates the offset relative to the player using the constants, scale and tilewidth.
    offset = pygame.math.Vector2(-player.x * scale * tileWidth + 2.5 * scale * tileWidth,
                                 -player.y * scale * tileWidth + 2.5 * scale * tileWidth)
    #Returns offset calculated 
    return offset
            
def drawGrid():
    for row in range(rows):
        for col in range(columns):
            tile = grid[row][col]
            tile.draw()

def generateLevel():
    global grid, rooms, entities, levelCount, rows, columns
    
    grid = []
    rooms = []
    entities = []

    #Increase room size as the level count increases
    rows = 28 + 5 * levelCount
    columns = 28 + 5 * levelCount
    
    for row in range(rows):
        grid.append([])
        for col in range(columns):
            tile = Tile(col, row, "wall")
            grid[row].append(tile)

    count = 0
    while True:
        if generateRoom() == "stop": break
        count += 1
    print(count)

    for i in range(len(rooms)):
        if i == 0: continue
        generateCorridor(rooms[i], rooms[i - 1])

    #Iterates through all the rooms
    for room in rooms:
        #Sets the tiletype of the entry point of each room to "door"
        room.door.tileType = "door"
        

def isRoomOverlapping(x, y, width, height):
    for room in rooms:
        if room.isRoomOverlapping(x, y, width, height): return True

def calculateRoomPositionAndSize():
    width = random.randint(8, 10)
    height = random.randint(8, 10)
    x = random.randint(2, columns - 2 - width)
    y = random.randint(2, rows - 2 - height)

    return width, height, x, y

def generateRoom():
    tries = 0
    width, height, x, y = calculateRoomPositionAndSize()
    while isRoomOverlapping(x, y, width, height):
        tries += 1
        if tries >= 500: return "stop"
        width, height, x, y = calculateRoomPositionAndSize()
    
    for row in range(height):
        for col in range(width):
            tile = grid[y + row][x + col]
            tile.tileType = "border"

    for row in range(height - 2):
        for col in range(width - 2):
            tile = grid[y + row + 1][x + col + 1]
            tile.tileType = "floor"

    grid[y][x].tileType = "wall"
    grid[y + height - 1][x].tileType = "wall"
    grid[y][x + width - 1].tileType = "wall"
    grid[y + height - 1][x + width - 1].tileType = "wall"

    room = Room(x, y, width, height)
    rooms.append(room)

def getDistanceFromTiles(tile1, tile2):
    tile1Pos = pygame.Vector2(tile1.x, tile1.y)
    tile2Pos = pygame.Vector2(tile2.x, tile2.y)
    distance = tile1Pos.distance_to(tile2Pos)
    return distance

def aStar(startTile, goalTile):
    frontier = queue.PriorityQueue()
    frontier.put(PrioritizedItem(0, startTile))
    
    cameFrom = dict()
    costSoFar = dict()
    cameFrom[startTile] = None
    costSoFar[startTile] = 0

    while not frontier.empty():   
        currentTile = frontier.get().item

        for nextTile in currentTile.getNeighbours():
            if nextTile == goalTile: return cameFrom, currentTile
            
            newCost = costSoFar[currentTile] + nextTile.getCost()
            
            if nextTile not in costSoFar or newCost < costSoFar[nextTile]:
                costSoFar[nextTile] = newCost
                cameFrom[nextTile] = currentTile
                
                priority = newCost + getDistanceFromTiles(nextTile, goalTile) 
                frontier.put(PrioritizedItem(priority, nextTile))

def generateCorridor(room1, room2):
    #Calculates path from room1's door to room2's door
    cameFrom, currentTile = aStar(room1.door, room2.door)
    #Backtracks the dictionary returned
    while currentTile in cameFrom:
        #Turns each tile within the dictionary into a floor
        currentTile.tileType = "floor"
        currentTile = cameFrom[currentTile]
    #The tile type of the entry point for both rooms are set to "floor"
    room1.door.tileType = "floor"
    room2.door.tileType = "floor"

#Function to get the first non-collidable tile
def getNextEmptyTile():
    #Iterates through the 2D array
    for row in range(rows):
        for col in range(columns):
            #Gets the tile at a position
            tile = grid[row][col]
            #Checks if the tile is not collidable, if it
            #isn't then return the tile whereas if it
            #is collidable then check the next tile
            if tile.tileType not in collidable:
                return tile

#Procedure which calls the draw method of every entity
def drawEntities():
    #Loops through all entities
    for entity in entities:
        #Calls each entity's draw method
        entity.draw()

def drawHUD():
    #Stores the rendered level font within a variable
    image = fonts["large"].render("Level " + str(levelCount), True, (255, 255, 255))
    #Draws the text to the screen
    screen.blit(image, (30, 30))

    #Draws score count onto the screen
    image = fonts["large"].render("Score: " + str(score), True, (255, 255, 255))
    screen.blit(image, (300, 30))

    #Stores the background bar's width
    barWidth = 100
    #Stores the width of the fill bar
    #based on the percentage of the players hitpoints
    fillWidth = 100 * player.hitpoints / player.maxHitpoints

    #Draws both bars
    pygame.draw.rect(screen, (255, 0, 0), (170, 35, barWidth, 25))
    pygame.draw.rect(screen, (7, 186, 22), (170, 35, fillWidth, 25))

    #Draws text displaying hitpoints in numerical form
    hitpointsText = str(player.hitpoints) + "/" + str(player.maxHitpoints) + "hp"
    image = fonts["medium"].render(hitpointsText, True, (255, 255, 255))
    screen.blit(image, (180, 40))

def drawButton(buttonName):
    #Gets the button's dictionary using the buttonName as a key
    button = buttons[buttonName]
    
    #Draws the button using its position and size values stored in the dictionary
    pygame.draw.rect(screen, (100, 100, 100), (button["position"], button["size"]))

    #Draws the text of the button using its text value stored in thedictionary
    image = fonts["medium"].render(button["text"], True, (255, 255, 255))
    screen.blit(image, (button["position"] + pygame.math.Vector2(10, 13)))

def drawEffects():
    for effect in effects:
        effect.draw()

#Draws all the necessary components within the game
def drawGame():
    #Fills the screen with black 
    screen.fill((0, 0, 0))
    #Draws the 2D array grid in a graphically representable form
    drawGrid()
    #Draws entities on-top of the grid
    drawEntities()
    #Draws effects on-top of entities
    drawEffects()
    #Draws the HUD on-top of everything
    drawHUD()
    #Draws buttons within the game
    for buttonName in gameButtons:
        drawButton(buttonName)
    
    #Updates the screen with everything that has just been drawn
    pygame.display.update()

#Draws all the necessary components within the main menu
def drawMainMenu():
    #Fills the screen with black 
    screen.fill((0, 0, 0))
    #Draws the title of the game
    image = fonts["large"].render("Dungeon crawler", True, (255, 255, 255))
    screen.blit(image, (30, 40))

    #Draws buttons within the main menu
    for buttonName in mainMenuButtons:
        drawButton(buttonName)
    
    #Updates the screen with everything that has just been drawn
    pygame.display.update()

#Draws all the necessary components within the settings menu
def drawSettings():
    #Fills the screen with black 
    screen.fill((0, 0, 0))
    #Draws the title of settings menu
    image = fonts["large"].render("Settings", True, (255, 255, 255))
    screen.blit(image, (30, 40))

    #Draws buttons within the main menu
    for buttonName in settingsButtons:
        drawButton(buttonName)
    
    #Updates the screen with everything that has just been drawn
    pygame.display.update()

def updateElements(elements):
    for element in elements:
        element.update()

def update():
    updateElements(rooms)
    updateElements(effects)
    player.update()

def spawnPlayer():
    global player
    
    #Gets the next empty tile
    spawnTile = getNextEmptyTile()
    #Insantiates a player object at position (5, 5)
    player = Player(spawnTile.x, spawnTile.y, "player")
    #Appends the player object into the entities list
    entities.append(player)

def exitGame():
    os._exit(0)

def toggleMusic():
    global musicEnabled

    #Adjusts volume accordingly depending on value
    #of the musicEnabled boolean
    if musicEnabled:
        pygame.mixer.music.set_volume(0)
    else:
        pygame.mixer.music.set_volume(0.2)

    #Switches the musicEnabled boolean to true/false
    musicEnabled = not musicEnabled

def toggleSound():
    global soundEnabled
    #Inverts the soundEnabled boolean
    soundEnabled = not soundEnabled

def processClick(buttonType):
    #Gets mouse position
    position = pygame.mouse.get_pos()
    #Cycles through all buttons
    for buttonName in buttons:
        #Checks if the button is of a particular type (such as main menu or game)
        #If it is not then look at the next button instead
        if buttonName not in buttonType: continue
        #Gets the button with buttonName as the key
        button = buttons[buttonName]

        #Checks if the mouse position is within the button's bounds
        xInBounds = button["position"].x <= position[0] <= button["position"].x + button["size"].x
        yInBounds = button["position"].y <= position[1] <= button["position"].y + button["size"].y

        #Checks if the conditions are true
        if xInBounds and yInBounds:
            #Performs the necessary function associated to the button
            button["onClick"]()
            #Returns the function as the button has been clicked
            return

def startGameFromMenu():
    global levelCount, score
    levelCount = 1
    score = 0
    game()

def newLevel():
    global levelCount
    #Increments level by 1
    levelCount += 1
    #Restarts game
    game()

def game():
    global run

    generateLevel()
    spawnPlayer()
    
    while run:
        clock.tick(60)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            elif event.type == pygame.MOUSEBUTTONUP:
                processClick(gameButtons)

        update()
        drawGame()

def mainMenu():
    global run
    
    while run:
        clock.tick(60)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            elif event.type == pygame.MOUSEBUTTONUP:
                processClick(mainMenuButtons)

        drawMainMenu()

def settings():
    global run

    while run:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            elif event.type == pygame.MOUSEBUTTONUP:
                processClick(settingsButtons)

        drawSettings()

#Stores all buttons
buttons = {
    "play" : {
        "text": "Play",
        "position" : pygame.math.Vector2(30, 100),
        "size" : pygame.math.Vector2(150, 40),
        "onClick" : startGameFromMenu
    },
    "settings" : {
        "text": "Settings",
        "position" : pygame.math.Vector2(30, 170),
        "size" : pygame.math.Vector2(150, 40),
        "onClick" : settings
    },
    "exit" : {
        "text": "Exit",
        "position" : pygame.math.Vector2(30, 240),
        "size" : pygame.math.Vector2(150, 40),
        "onClick" : exitGame
    },
    "home" : {
        "text": "Home",
        "position" : pygame.math.Vector2(485, 525),
        "size" : pygame.math.Vector2(100, 40),
        "onClick" : mainMenu
    },
    "toggleMusic" : {
        "text": "Toggle music",
        "position" : pygame.math.Vector2(30, 100),
        "size" : pygame.math.Vector2(150, 40),
        "onClick" : toggleMusic
    },
    "toggleSound" : {
        "text": "Toggle sound",
        "position" : pygame.math.Vector2(30, 170),
        "size" : pygame.math.Vector2(150, 40),
        "onClick" : toggleSound
    }
}
    
run = True

mainMenu()
    
pygame.quit()
