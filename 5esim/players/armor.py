armor = 0
cost = 0

armor_dict = {
    "light_armor": {
        "unarmored":{
            "armor":int(10),
            "cost":int(0)
        },
        "padded":{
            "armor":int(11),
            "cost":int(5)
        },
        "leather":{
            "armor":int(12),
            "cost":int(10)
        },
        "studded_leather":{
            "armor":int(13),
            "cost":int(45)
        }
    },

    "medium_armor": {
        "hide":{
            "armor":int(12),
            "cost":int(10)
        },
        "chain_shirt":{
            "armor":int(13),
            "cost":int(50)
        },
        "breastplate":{
            "armor":int(14),
            "cost":int(400)
        },
        "half_plate":{
            "armor":int(15),
            "cost":int(750)
        }
    },

    "heavy_armor": {
        "ring_mail":{
            "ac":int(14),
            "cost":int(30)
        },
        "chain_mail":{
            "ac":int(16),
            "cost":int(75)
        },
        "splint":{
            "ac":int(17),
            "cost":int(200)
        },
        "plate":{
            "ac":int(18),
            "cost":int(1500)
        }
    },

    'shields':{
        "buckler":{
            "ac":int(1),
            "cost":int(10)
        },
        "shield":{
            "ac":int(2),
            "cost":int(25)
        },
        "kite_shield":{
            "ac":int(3),
            "cost":int(50)
        }
    }
}