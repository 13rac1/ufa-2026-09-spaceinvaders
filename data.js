export const DATA = {
 "entry": {
  "rows": [
   {
    "player": "code",
    "name": "Code Autopilot",
    "input": "its own rules",
    "games": 5,
    "score": 3180,
    "scores": [
     800.0,
     3570.0,
     3780.0,
     3785.0,
     3965.0
    ],
    "latency_ms": 0.0,
    "cost": 0.0
   },
   {
    "player": "jev-t3",
    "name": "JEV",
    "input": "Tier 3: code verdicts (reference)",
    "games": 5,
    "score": 2154,
    "scores": [
     840.0,
     1920.0,
     2335.0,
     2745.0,
     2930.0
    ],
    "latency_ms": 98.62,
    "cost": 5.6455564815516325e-05
   },
   {
    "player": "always-fire",
    "name": "Always FIRE",
    "input": "none",
    "games": 5,
    "score": 285,
    "scores": [
     285.0,
     285.0,
     285.0,
     285.0,
     285.0
    ],
    "latency_ms": 0.0,
    "cost": 0.0
   },
   {
    "player": "jev-t1",
    "name": "JEV",
    "input": "Tier 1",
    "games": 5,
    "score": 221,
    "scores": [
     105.0,
     110.0,
     180.0,
     300.0,
     410.0
    ],
    "latency_ms": 92.06,
    "cost": 3.943915343915344e-05
   },
   {
    "player": "jev-t2",
    "name": "JEV",
    "input": "Tier 2",
    "games": 5,
    "score": 194,
    "scores": [
     135.0,
     155.0,
     210.0,
     230.0,
     240.0
    ],
    "latency_ms": 93.31,
    "cost": 3.784700931770364e-05
   },
   {
    "player": "qwen-t2",
    "name": "Qwen3.8 27B",
    "input": "Tier 2",
    "games": 2,
    "score": 185,
    "scores": [
     50.0,
     320.0
    ],
    "latency_ms": 2292.55,
    "cost": 0.0
   },
   {
    "player": "random",
    "name": "Random",
    "input": "none",
    "games": 5,
    "score": 125,
    "scores": [
     30.0,
     110.0,
     120.0,
     140.0,
     225.0
    ],
    "latency_ms": 0.01,
    "cost": 0.0
   },
   {
    "player": "qwen-t1",
    "name": "Qwen3.8 27B",
    "input": "Tier 1",
    "games": 5,
    "score": 113,
    "scores": [
     50.0,
     105.0,
     105.0,
     105.0,
     200.0
    ],
    "latency_ms": 2440.67,
    "cost": 0.0
   },
   {
    "player": "llm-t1",
    "name": "Haiku 4.5",
    "input": "Tier 1",
    "games": 5,
    "score": 105,
    "scores": [
     35.0,
     55.0,
     80.0,
     125.0,
     230.0
    ],
    "latency_ms": 1071.74,
    "cost": 0.0013913962804005724
   },
   {
    "player": "llm-t2",
    "name": "Haiku 4.5",
    "input": "Tier 2",
    "games": 5,
    "score": 103,
    "scores": [
     15.0,
     40.0,
     40.0,
     135.0,
     285.0
    ],
    "latency_ms": 1063.64,
    "cost": 0.0014000042372881356
   }
  ],
  "human": 1668.7,
  "random_ref": 148.0,
  "code_all": 2682,
  "code_all_n": 20,
  "realtime": {
   "jev": [
    221,
    198
   ],
   "code": [
    3180,
    3180
   ]
  }
 },
 "code_versions": [
  {
   "version": "v3",
   "score": 2306,
   "games": 20
  },
  {
   "version": "v4",
   "score": 2365,
   "games": 20
  },
  {
   "version": "v5",
   "score": 2682,
   "games": 20
  }
 ],
 "code_version_now": "v5",
 "example": {
  "image": "assets/frames/example.png",
  "tiers": {
   "1": {
    "state": {
     "ship": {
      "x": 39,
      "lives": 3
     },
     "gun_ready": true,
     "player_shot": null,
     "alien_bullets": [
      {
       "x": 106,
       "y": 126,
       "vy": 1.0
      }
     ],
     "alien_rows": [
      {
       "y": 35,
       "x": [
        26,
        42,
        58,
        74,
        90,
        106
       ]
      },
      {
       "y": 53,
       "x": [
        26,
        42,
        58,
        74,
        90,
        106
       ]
      },
      {
       "y": 72,
       "x": [
        26,
        42,
        58,
        74,
        90,
        106
       ]
      },
      {
       "y": 89,
       "x": [
        26,
        42,
        58,
        74,
        90,
        106
       ]
      },
      {
       "y": 107,
       "x": [
        26,
        42,
        58,
        74,
        90,
        106
       ]
      },
      {
       "y": 125,
       "x": [
        26,
        42,
        58,
        74,
        90,
        106
       ]
      }
     ],
     "fleet_vx": 0.0312,
     "shields": [
      {
       "x0": 42,
       "x1": 49
      },
      {
       "x0": 74,
       "x1": 81
      },
      {
       "x0": 106,
       "x1": 113
      }
     ],
     "mothership": null
    },
    "questions": {
     "action": {
      "type": "choice",
      "instructions": "Space Invaders, screen pixels, x to the right, y down. The ship is 7 px wide and moves 0.5 px per frame; one step is 4 frames. Its shot rises 2 px per frame, one shot at a time. Alien bullets fall 1 px per frame; a bullet that reaches the ship's rows (y 185-194) within 3 px of its center destroys it. Shields (y 157-174) stop shots and bullets. The game ends when the aliens reach the shields. Choose the ship's action for the next step. fleet_vx is the fleet's speed in px per frame; it turns at the screen edges.",
      "criteria": {
       "NOOP": "Stay in place; no shot.",
       "FIRE": "Stay in place and fire (only possible when gun_ready is true).",
       "RIGHT": "Move right 2 px; no shot.",
       "LEFT": "Move left 2 px; no shot.",
       "RIGHTFIRE": "Move right 2 px and fire.",
       "LEFTFIRE": "Move left 2 px and fire."
      }
     }
    }
   },
   "2": {
    "state": {
     "lives": 3,
     "gun_ready": true,
     "shield_above_ship": false,
     "room_to_move_px": {
      "left": 2,
      "right": 80
     },
     "alien_bullets": [
      {
       "lane": "right",
       "arrival": "far",
       "dx": 67,
       "frames_to_ship_row": 51,
       "stopped_by_shield": true
      }
     ],
     "lowest_row_aliens": [
      {
       "side": "left",
       "dx_at_shot_arrival": -13,
       "behind_shield": false
      },
      {
       "side": "over_ship",
       "dx_at_shot_arrival": 3,
       "behind_shield": true
      },
      {
       "side": "right",
       "dx_at_shot_arrival": 19,
       "behind_shield": false
      },
      {
       "side": "right",
       "dx_at_shot_arrival": 35,
       "behind_shield": true
      },
      {
       "side": "right",
       "dx_at_shot_arrival": 51,
       "behind_shield": false
      },
      {
       "side": "right",
       "dx_at_shot_arrival": 67,
       "behind_shield": true
      }
     ],
     "other_aliens": 30,
     "mothership": null
    },
    "questions": {
     "action": {
      "type": "choice",
      "instructions": "Space Invaders. Offsets are px, negative to the left. Bullet dx is from the ship's center; alien and mothership dx is from the shot's column at the moment a shot fired now would reach them. lane over_ship: the bullet is within the ship's width; side over_ship: a shot fired now reaches that alien. arrival: now 0-8 frames, soon 9-30, far more. The ship is 7 px wide and moves 0.5 px per frame; one step is 4 frames. Its shot rises 2 px per frame, one shot at a time. Alien bullets fall 1 px per frame; a bullet that reaches the ship's rows (y 185-194) within 3 px of its center destroys it. Shields (y 157-174) stop shots and bullets. The game ends when the aliens reach the shields. Choose the ship's action for the next step.",
      "criteria": {
       "NOOP": "Stay in place; no shot.",
       "FIRE": "Stay in place and fire (only possible when gun_ready is true).",
       "RIGHT": "Move right 2 px; no shot.",
       "LEFT": "Move left 2 px; no shot.",
       "RIGHTFIRE": "Move right 2 px and fire.",
       "LEFTFIRE": "Move left 2 px and fire."
      }
     }
    }
   },
   "3": {
    "state": {
     "features": {
      "can_fire": true,
      "safe_left": true,
      "safe_stay": true,
      "safe_right": true,
      "target_dx": 19,
      "target_kind": "alien",
      "aligned": false,
      "under_shield": false,
      "target_behind_shield": false,
      "nearest_threat": null
     },
     "ship_x": 39,
     "lives": 3,
     "aliens_left": 36,
     "aliens": [
      {
       "x": 26,
       "y": 35
      },
      {
       "x": 42,
       "y": 35
      },
      {
       "x": 58,
       "y": 35
      },
      {
       "x": 74,
       "y": 35
      },
      {
       "x": 90,
       "y": 35
      },
      {
       "x": 106,
       "y": 35
      },
      {
       "x": 26,
       "y": 53
      },
      {
       "x": 42,
       "y": 53
      },
      {
       "x": 58,
       "y": 53
      },
      {
       "x": 74,
       "y": 53
      },
      {
       "x": 90,
       "y": 53
      },
      {
       "x": 106,
       "y": 53
      },
      {
       "x": 26,
       "y": 72
      },
      {
       "x": 42,
       "y": 72
      },
      {
       "x": 58,
       "y": 72
      },
      {
       "x": 74,
       "y": 72
      },
      {
       "x": 90,
       "y": 72
      },
      {
       "x": 106,
       "y": 72
      },
      {
       "x": 26,
       "y": 89
      },
      {
       "x": 42,
       "y": 89
      },
      {
       "x": 58,
       "y": 89
      },
      {
       "x": 74,
       "y": 89
      },
      {
       "x": 90,
       "y": 89
      },
      {
       "x": 106,
       "y": 89
      },
      {
       "x": 26,
       "y": 107
      },
      {
       "x": 42,
       "y": 107
      },
      {
       "x": 58,
       "y": 107
      },
      {
       "x": 74,
       "y": 107
      },
      {
       "x": 90,
       "y": 107
      },
      {
       "x": 106,
       "y": 107
      },
      {
       "x": 26,
       "y": 125
      },
      {
       "x": 42,
       "y": 125
      },
      {
       "x": 58,
       "y": 125
      },
      {
       "x": 74,
       "y": 125
      },
      {
       "x": 90,
       "y": 125
      },
      {
       "x": 106,
       "y": 125
      }
     ],
     "alien_bullets": [
      {
       "x": 106,
       "y": 126
      }
     ],
     "player_shot": {
      "x": null,
      "y": null
     },
     "shields": [
      {
       "x0": 42,
       "x1": 49,
       "pixels": 112
      },
      {
       "x0": 74,
       "x1": 81,
       "pixels": 112
      },
      {
       "x0": 106,
       "x1": 113,
       "pixels": 112
      }
     ],
     "mothership": null,
     "fleet_vx": 0.0312
    },
    "questions": {
     "action": {
      "type": "choice",
      "instructions": "Choose the action for the ship in this Space Invaders frame. The features field holds the computed facts; use them first. Never move to a side whose safe_left or safe_right is false. Priority: 1) if safe_stay is false, dodge: go left when nearest_threat.dx >= 0 (the bullet is right of or above the ship) and safe_left is true, else go right if safe_right is true; 2) otherwise, if aligned is false, move toward the target (target_dx > 0: right, < 0: left) if that side is safe, else stay; 3) fire only when aligned is true and can_fire is true.",
      "criteria": {
       "NOOP": "Stay and do not fire. Right when safe_stay is true and there is nothing to do now: aligned is true but can_fire is false; or the side toward the target is not safe (target_dx > 0 with safe_right false, or target_dx < 0 with safe_left false); or target_dx is null. Also right when no move is safe.",
       "FIRE": "Stay and fire: safe_stay is true, aligned is true, and can_fire is true.",
       "RIGHT": "Move right without firing. Dodge: safe_stay is false, safe_right is true, and either nearest_threat.dx < 0 or safe_left is false. Or approach: safe_stay is true, aligned is false, target_dx > 0, and safe_right is true.",
       "LEFT": "Move left without firing. Dodge: safe_stay is false, safe_left is true, and nearest_threat.dx >= 0. Or approach: safe_stay is true, aligned is false, target_dx < 0, and safe_left is true.",
       "RIGHTFIRE": "Move right and fire: the dodge case of RIGHT holds, and aligned is true and can_fire is true.",
       "LEFTFIRE": "Move left and fire: the dodge case of LEFT holds, and aligned is true and can_fire is true."
      }
     }
    }
   }
  }
 },
 "quiz": [
  {
   "image": "assets/frames/approach-2.png",
   "kind": "approach",
   "seed": 12,
   "code_action": "LEFT",
   "right": [
    "LEFT",
    "LEFTFIRE"
   ],
   "reason": "The target is 5 px to the left (where it will be when a shot arrives). Firing now would miss.",
   "tier1": {
    "ship": {
     "x": 100,
     "lives": 3
    },
    "gun_ready": false,
    "player_shot": {
     "x": 101,
     "y": 114
    },
    "alien_bullets": [
     {
      "x": 106,
      "y": 118,
      "vy": 1.0
     }
    ],
    "alien_rows": [
     {
      "y": 75,
      "x": [
       27,
       43,
       59,
       75,
       91,
       107
      ]
     },
     {
      "y": 93,
      "x": [
       27,
       43,
       59,
       75
      ]
     },
     {
      "y": 111,
      "x": [
       59,
       75,
       91
      ]
     },
     {
      "y": 129,
      "x": [
       59,
       75,
       91
      ]
     }
    ],
    "fleet_vx": 0.0909,
    "shields": [
     {
      "x0": 43,
      "x1": 49
     },
     {
      "x0": 74,
      "x1": 81
     },
     {
      "x0": 107,
      "x1": 113
     }
    ],
    "mothership": {
     "x": 117.0,
     "vx": -0.25
    }
   }
  },
  {
   "image": "assets/frames/approach-0.png",
   "kind": "approach",
   "seed": 11,
   "code_action": "RIGHT",
   "right": [
    "RIGHT",
    "RIGHTFIRE"
   ],
   "reason": "The target is 5 px to the right (where it will be when a shot arrives). Firing now would miss.",
   "tier1": {
    "ship": {
     "x": 89,
     "lives": 3
    },
    "gun_ready": true,
    "player_shot": null,
    "alien_bullets": [
     {
      "x": 82,
      "y": 144,
      "vy": 1.0
     }
    ],
    "alien_rows": [
     {
      "y": 115,
      "x": [
       82,
       98,
       114
      ]
     },
     {
      "y": 133,
      "x": [
       82,
       98,
       114
      ]
     },
     {
      "y": 152,
      "x": [
       98
      ]
     }
    ],
    "fleet_vx": -0.1875,
    "shields": [],
    "mothership": {
     "x": 26.0,
     "vx": -0.25
    }
   }
  },
  {
   "image": "assets/frames/fire-0.png",
   "kind": "fire",
   "seed": 2,
   "code_action": "FIRE",
   "right": [
    "FIRE",
    "RIGHTFIRE",
    "LEFTFIRE"
   ],
   "reason": "The target will be right above the gun when the shot gets there, and the gun is ready.",
   "tier1": {
    "ship": {
     "x": 94,
     "lives": 3
    },
    "gun_ready": true,
    "player_shot": null,
    "alien_bullets": [
     {
      "x": 83,
      "y": 150,
      "vy": 1.0
     },
     {
      "x": 81,
      "y": 184,
      "vy": 1.0
     }
    ],
    "alien_rows": [
     {
      "y": 135,
      "x": [
       50,
       82,
       98,
       114,
       130
      ]
     },
     {
      "y": 153,
      "x": [
       50,
       98,
       114,
       130
      ]
     }
    ],
    "fleet_vx": -0.0909,
    "shields": [],
    "mothership": null
   }
  },
  {
   "image": "assets/frames/wall-0.png",
   "kind": "wall",
   "seed": 20,
   "code_action": "RIGHT",
   "right": [
    "NOOP",
    "FIRE",
    "RIGHT",
    "RIGHTFIRE"
   ],
   "reason": "The ship is against the left wall. Moving left does nothing; the code waits or heads for its target.",
   "tier1": {
    "ship": {
     "x": 37,
     "lives": 3
    },
    "gun_ready": true,
    "player_shot": null,
    "alien_bullets": [],
    "alien_rows": [
     {
      "y": 35,
      "x": [
       25,
       41,
       57,
       73,
       89,
       105
      ]
     },
     {
      "y": 53,
      "x": [
       25,
       41,
       57,
       73,
       89,
       105
      ]
     },
     {
      "y": 71,
      "x": [
       25,
       41,
       57,
       73,
       89,
       105
      ]
     },
     {
      "y": 89,
      "x": [
       25,
       41,
       57,
       73,
       89,
       105
      ]
     },
     {
      "y": 107,
      "x": [
       25,
       41,
       57,
       73,
       89,
       105
      ]
     },
     {
      "y": 125,
      "x": [
       25,
       41,
       57,
       73,
       89,
       105
      ]
     }
    ],
    "fleet_vx": 0.0312,
    "shields": [
     {
      "x0": 42,
      "x1": 49
     },
     {
      "x0": 74,
      "x1": 81
     },
     {
      "x0": 106,
      "x1": 113
     }
    ],
    "mothership": null
   }
  },
  {
   "image": "assets/frames/danger-0.png",
   "kind": "danger",
   "seed": 14,
   "code_action": "LEFT",
   "right": [
    "RIGHT",
    "LEFT",
    "RIGHTFIRE",
    "LEFTFIRE"
   ],
   "reason": "An alien bullet would hit the ship if it stayed. Moving left is safe.",
   "tier1": {
    "ship": {
     "x": 89,
     "lives": 3
    },
    "gun_ready": true,
    "player_shot": null,
    "alien_bullets": [
     {
      "x": 91,
      "y": 152,
      "vy": 1.0
     }
    ],
    "alien_rows": [
     {
      "y": 75,
      "x": [
       42,
       58,
       74,
       90,
       106,
       122
      ]
     },
     {
      "y": 93,
      "x": [
       42,
       58,
       74,
       90,
       106,
       122
      ]
     },
     {
      "y": 112,
      "x": [
       42,
       58,
       74,
       90,
       122
      ]
     },
     {
      "y": 129,
      "x": [
       58,
       74,
       122
      ]
     },
     {
      "y": 147,
      "x": [
       122
      ]
     },
     {
      "y": 165,
      "x": [
       122
      ]
     }
    ],
    "fleet_vx": -0.0156,
    "shields": [],
    "mothership": {
     "x": 87.0,
     "vx": 0.25
    }
   }
  },
  {
   "image": "assets/frames/approach-1.png",
   "kind": "approach",
   "seed": 19,
   "code_action": "LEFT",
   "right": [
    "LEFT",
    "LEFTFIRE"
   ],
   "reason": "The target is 22 px to the left (where it will be when a shot arrives). Firing now would miss.",
   "tier1": {
    "ship": {
     "x": 81,
     "lives": 3
    },
    "gun_ready": true,
    "player_shot": null,
    "alien_bullets": [
     {
      "x": 42,
      "y": 190,
      "vy": 1.0
     }
    ],
    "alien_rows": [
     {
      "y": 165,
      "x": [
       50
      ]
     }
    ],
    "fleet_vx": 1.25,
    "shields": [],
    "mothership": null
   }
  },
  {
   "image": "assets/frames/wall-1.png",
   "kind": "wall",
   "seed": 16,
   "code_action": "FIRE",
   "right": [
    "NOOP",
    "FIRE",
    "RIGHT",
    "RIGHTFIRE"
   ],
   "reason": "The ship is against the left wall. Moving left does nothing; the code waits or heads for its target.",
   "tier1": {
    "ship": {
     "x": 37,
     "lives": 3
    },
    "gun_ready": true,
    "player_shot": null,
    "alien_bullets": [],
    "alien_rows": [
     {
      "y": 75,
      "x": [
       25,
       41,
       57,
       73,
       89,
       105
      ]
     },
     {
      "y": 93,
      "x": [
       25,
       41,
       57,
       73,
       89,
       105
      ]
     },
     {
      "y": 111,
      "x": [
       25,
       41,
       57,
       73,
       89,
       105
      ]
     },
     {
      "y": 129,
      "x": [
       25,
       41,
       57,
       73,
       89,
       105
      ]
     },
     {
      "y": 147,
      "x": [
       25,
       41,
       57,
       73,
       89,
       105
      ]
     },
     {
      "y": 165,
      "x": [
       25,
       41,
       57,
       73,
       89,
       105
      ]
     }
    ],
    "fleet_vx": 0.0312,
    "shields": [],
    "mothership": null
   }
  },
  {
   "image": "assets/frames/fire-2.png",
   "kind": "fire",
   "seed": 16,
   "code_action": "FIRE",
   "right": [
    "FIRE",
    "RIGHTFIRE",
    "LEFTFIRE"
   ],
   "reason": "The target will be right above the gun when the shot gets there, and the gun is ready.",
   "tier1": {
    "ship": {
     "x": 61,
     "lives": 3
    },
    "gun_ready": true,
    "player_shot": null,
    "alien_bullets": [
     {
      "x": 45,
      "y": 118,
      "vy": 1.0
     }
    ],
    "alien_rows": [
     {
      "y": 105,
      "x": [
       48,
       64,
       80,
       96
      ]
     },
     {
      "y": 123,
      "x": [
       64,
       80
      ]
     }
    ],
    "fleet_vx": 0.1875,
    "shields": [],
    "mothership": {
     "x": 80.0,
     "vx": -0.25
    }
   }
  },
  {
   "image": "assets/frames/danger-1.png",
   "kind": "danger",
   "seed": 13,
   "code_action": "LEFT",
   "right": [
    "RIGHT",
    "LEFT",
    "RIGHTFIRE",
    "LEFTFIRE"
   ],
   "reason": "An alien bullet would hit the ship if it stayed. Moving left is safe.",
   "tier1": {
    "ship": {
     "x": 68,
     "lives": 3
    },
    "gun_ready": true,
    "player_shot": null,
    "alien_bullets": [
     {
      "x": 36,
      "y": 92,
      "vy": 1.0
     },
     {
      "x": 72,
      "y": 152,
      "vy": 1.0
     }
    ],
    "alien_rows": [
     {
      "y": 65,
      "x": [
       34,
       50,
       66,
       82,
       98,
       114
      ]
     },
     {
      "y": 83,
      "x": [
       50,
       66,
       82,
       98
      ]
     },
     {
      "y": 102,
      "x": [
       50,
       66,
       82,
       98
      ]
     },
     {
      "y": 119,
      "x": [
       50
      ]
     },
     {
      "y": 137,
      "x": [
       50
      ]
     }
    ],
    "fleet_vx": -0.0909,
    "shields": [
     {
      "x0": 42,
      "x1": 49
     },
     {
      "x0": 74,
      "x1": 81
     },
     {
      "x0": 106,
      "x1": 113
     }
    ],
    "mothership": null
   }
  },
  {
   "image": "assets/frames/fire-1.png",
   "kind": "fire",
   "seed": 10,
   "code_action": "FIRE",
   "right": [
    "FIRE",
    "RIGHTFIRE",
    "LEFTFIRE"
   ],
   "reason": "The target will be right above the gun when the shot gets there, and the gun is ready.",
   "tier1": {
    "ship": {
     "x": 52,
     "lives": 3
    },
    "gun_ready": true,
    "player_shot": null,
    "alien_bullets": [
     {
      "x": 65,
      "y": 150,
      "vy": 1.0
     }
    ],
    "alien_rows": [
     {
      "y": 75,
      "x": [
       50,
       66,
       82,
       98,
       114,
       130
      ]
     },
     {
      "y": 93,
      "x": [
       50,
       66,
       82,
       98,
       114,
       130
      ]
     },
     {
      "y": 111,
      "x": [
       50,
       66,
       82,
       98,
       114,
       130
      ]
     },
     {
      "y": 129,
      "x": [
       50,
       82,
       98,
       114,
       130
      ]
     },
     {
      "y": 147,
      "x": [
       50,
       114,
       130
      ]
     },
     {
      "y": 165,
      "x": [
       50,
       130
      ]
     }
    ],
    "fleet_vx": 0.0312,
    "shields": [],
    "mothership": null
   }
  }
 ],
 "after": {
  "code_steps": [
   {
    "version": "v3",
    "rule": "Shoot the lowest alien of an edge column first: a narrower fleet travels further before each drop.",
    "tuning": "+526 and +424 points per game over v2 on two tuning seed sets"
   },
   {
    "version": "v4",
    "rule": "While a shot is flying, already move to the next target.",
    "tuning": "+197 points per game over v3 on 400 fresh tuning seeds (better on 225)"
   },
   {
    "version": "v5",
    "rule": "When the aliens are one drop from landing, clear the lowest row first.",
    "tuning": "+399 and +381 points per game over v4 on two tuning seed sets"
   }
  ],
  "failed": [
   [
    "Fire at any alien a shot would hit",
    "-1,281"
   ],
   [
    "Fire only when a hit is predicted",
    "-524"
   ],
   [
    "Aim for the alien that leaves the most time",
    "about -800"
   ],
   [
    "Lowest alien first once 8 aliens are left",
    "-257"
   ]
  ],
  "strategy": {
   "labels": [
    "Move toward the target",
    "Dodge a bullet",
    "Fire when lined up"
   ],
   "jev": [
    [
     0.11,
     0.6
    ],
    [
     0.16,
     0.89
    ],
    [
     1.0,
     0.97
    ]
   ],
   "haiku": [
    [
     0.32,
     0.39
    ],
    [
     0.53,
     0.68
    ],
    [
     0.44,
     0.13
    ]
   ],
   "qwen": [
    [
     0.03,
     0.04
    ],
    [
     0.07,
     0.08
    ],
    [
     0.33,
     0.22
    ]
   ],
   "jev_games": 174
  },
  "waves": [
   {
    "wave": 1,
    "start_y": 125,
    "cleared": 82,
    "invaded": 17
   },
   {
    "wave": 2,
    "start_y": 135,
    "cleared": 68,
    "invaded": 14
   },
   {
    "wave": 3,
    "start_y": 145,
    "cleared": 62,
    "invaded": 6
   },
   {
    "wave": 4,
    "start_y": 155,
    "cleared": 50,
    "invaded": 12
   },
   {
    "wave": 5,
    "start_y": 165,
    "cleared": 3,
    "invaded": 47
   }
  ]
 },
 "actions": [
  "NOOP",
  "FIRE",
  "RIGHT",
  "LEFT",
  "RIGHTFIRE",
  "LEFTFIRE"
 ],
 "narrow": {
  "questions": [
   {
    "question": "Will a bullet hit if the ship stays?",
    "right": 0.7066666666666667,
    "guess": 0.75
   },
   {
    "question": "Which side is safe to move to?",
    "right": 0.8433333333333334,
    "guess": 0.8533333333333334
   },
   {
    "question": "Where will the nearest target be when a shot arrives?",
    "right": 0.27666666666666667,
    "guess": 0.6266666666666667
   },
   {
    "question": "Would a shot fired now hit?",
    "right": 0.39666666666666667,
    "guess": 0.64
   }
  ],
  "frames": 300,
  "fired": {
   "lined_up": [
    304,
    305
   ],
   "not_lined_up": [
    744,
    746
   ]
  }
 }
};
