#ifndef DOA_SATURN_ACTION_TYPES_H
#define DOA_SATURN_ACTION_TYPES_H

/*
 * Types recovered from the Sega Saturn DOA1 act/act.c padding fragment.
 * Names are prefixed so this header can be parsed into Ghidra without
 * colliding with SDK or pre-existing project types.
 *
 * Pointer widths are 32-bit on both SH-2 and i960.  DOA_FIXED is signed 16.16
 * fixed point where the original source used FIXED.
 *
 * Confidence:
 * - DOA_COMACT, DOA_DERVACT, DOA_DOWNACT, DOA_COMTRW and DOA_COMBODAT have
 *   byte-exact source definitions.
 * - DOA_COMDAT has a byte-exact logical definition but contains pointers.
 * - DOA_COMCTRL should be treated as a semantic field list until compiler
 *   padding is verified independently on each CPU.
 * - DOA_ARCADE_PLAYER and DOA_ARCADE_PLAYER_KNOWN are Model 2 runtime views,
 *   derived from the long-term cross-build map, cheats, and live observations
 *   rather than Saturn source.  The full view preserves established field
 *   names; individual unknown semantics still need runtime confirmation.
 * - DOA_COND_BRANCH and DOA_ORDERACT are arcade-derived from the AI selector
 *   functions.  Their trailing +4/+6 fields remain provisionally named
 *   pending more runtime evidence.
 */

typedef unsigned char  DOA_U8;
typedef signed short   DOA_S16;
typedef unsigned short DOA_U16;
typedef signed int     DOA_S32;
typedef unsigned int   DOA_U32;
typedef float          DOA_F32;
typedef DOA_S32        DOA_FIXED;
typedef DOA_U32        DOA_ADRSINT;

enum DOA_COMBO_COMMAND {
    DOA_CMB_ACT = 0,
    DOA_CMB_BAK,
    DOA_CMB_DER,
    DOA_CMB_JUMP,
    DOA_CMB_NOW,
    DOA_CMB_TRW,
    DOA_CMB_GRSP,
    DOA_CMB_DOWN,
    DOA_CMB_WAIT,
    DOA_CMB_RNDWT,
    DOA_CMB_LVLWT,
    DOA_CMB_DELAY,
    DOA_CMB_RNDDELAY,
    DOA_CMB_KEEP,
    DOA_CMB_RNDKEEP,
    DOA_CMB_LVLKEEP,
    DOA_CMB_KEEP_ESTA,
    DOA_CMB_KEEP_EATK,
    DOA_CMB_ATIME,
    DOA_CMB_ACTSTA,
    DOA_CMB_ACTCODE,
    DOA_CMB_CHK_BLW,
    DOA_CMB_CHK_HIT,
    DOA_CMB_CHK_NOHIT,
    DOA_CMB_CHK_EATK,
    DOA_CMB_BRA,
    DOA_CMB_BRA_BLW,
    DOA_CMB_BRA_HIT,
    DOA_CMB_BRA_NOHIT,
    DOA_CMB_BRA_ACODE,
    DOA_CMB_GROUP,
    DOA_CMB_DER_GROUP,
    DOA_CMB_ORDER,
    DOA_CMB_CALL,
    DOA_CMB_END
};

typedef struct DOA_COMACT {
    DOA_U8 per;
    DOA_U8 actreq;
    DOA_U8 para;
    DOA_U8 lvl;
} DOA_COMACT;

/*
 * Arcade conditional-action record selected through the 0xB52C0 family.
 * FUN_0002D560 forwards set_num/check_condition back into itself.  The two
 * trailing fields are passed/retained as 16-bit values but are zero in every
 * currently decoded doa/doaa record, so their semantics remain provisional.
 */
typedef struct DOA_COND_BRANCH {
    DOA_U16 weight;
    DOA_U8 set_num;
    DOA_U8 check_condition;
    DOA_U16 weight_adjustment;
    DOA_U16 reserved;
} DOA_COND_BRANCH;

/*
 * Arcade ordered-action record selected through the 0xB5B70 family.
 * Positive repeat_count_or_opcode values advance after that many accepted
 * evaluations.  -1 ends/fails, -2 resets to entry zero, and -3 jumps to the
 * entry index held in set_num.  FUN_0002D7C0 does not read +4 or +6.
 */
typedef struct DOA_ORDERACT {
    DOA_S16 repeat_count_or_opcode;
    DOA_U8 set_num;
    DOA_U8 check_condition;
    DOA_U16 unknown_04;
    DOA_U16 unknown_06;
} DOA_ORDERACT;

typedef struct DOA_DERVACT {
    DOA_U8 now_act;
    DOA_U8 derv_act;
    DOA_U8 slip_act;
} DOA_DERVACT;

typedef struct DOA_DOWNACT {
    DOA_U8 act_time;
    DOA_U8 downa_act;
} DOA_DOWNACT;

typedef struct DOA_COMTRW {
    DOA_U8 throw_success;
    DOA_U8 throw_failure;
} DOA_COMTRW;

typedef struct DOA_COMBODAT {
    DOA_U8 cmb_cmd;
    DOA_U8 cmb_act;
} DOA_COMBODAT;

typedef struct DOA_COMLVL {
    DOA_U8 of_wait_min, of_wait_lmt;
    DOA_U8 df_wait_min, df_wait_lmt;
    DOA_U8 der_wait_min, der_wait_lmt;
    DOA_U8 move_per;
    DOA_U8 blow_cont;
    DOA_U8 caution_per;
    DOA_U8 react_min;
    DOA_U8 react_up;
    DOA_U8 df_react_min, df_react_lmt;
    DOA_U8 derv_per;
    DOA_U8 slip_per;
    DOA_U8 throw_slip_per;
    DOA_U8 stgg_rcv_spd;
    DOA_U8 down_rcv_spd;
    DOA_U8 getup_per;
    DOA_U8 getup_der_per;
    DOA_U8 excombo_per;
    DOA_U8 downa_per;
    DOA_U8 ukemi_per_min;
    DOA_U8 ukemi_per_cng;
} DOA_COMLVL;

typedef struct DOA_COMPSNL {
    DOA_FIXED range_short;
    DOA_FIXED range_middle;
    DOA_FIXED range_long;
    DOA_FIXED excombo_hi;
    DOA_FIXED excombo_md;
    DOA_U8 of_per[4];
    DOA_U8 df_per[4];
    DOA_U8 mid_k_grsp;
} DOA_COMPSNL;

typedef struct DOA_COMACTPER {
    DOA_U8 per[4];
    DOA_U16 per_total;
} DOA_COMACTPER;

typedef struct DOA_COMDAT {
    DOA_ADRSINT act_dat;
    DOA_COMACT **group_dat;
    DOA_COMBODAT **combo_dat;
    DOA_COMPSNL *psnl_dat;
} DOA_COMDAT;

typedef struct DOA_COMCTRL {
    DOA_S16 act_wait;
    DOA_U8 der_wait_flg;
    DOA_S16 der_wait;
    DOA_U8 combo_flg;
    DOA_S16 combo_wait;
    DOA_COMBODAT *combo_adrs;
    DOA_COMBODAT *combo_ret_adrs;
    DOA_U8 act_flg;
    DOA_U8 downa_flg;
    DOA_U8 ukemi_flg;
    DOA_U8 caution_flg;
    DOA_U8 counter_flg;
    DOA_U8 start_flg;
    DOA_U8 now_cond;
    DOA_U8 now_type;
    DOA_U8 blow_flg;
    DOA_U8 blow_hi;
    DOA_U8 blow_hit;
    DOA_U8 blow_chk;
    DOA_U8 react_type;
    DOA_U8 react_per;
    DOA_U8 old_react_type;
    DOA_U8 old_react_per;
    DOA_U8 actsta_old;
    DOA_U8 vs_getup_hi;
    DOA_COMACTPER actper_of;
    DOA_COMACTPER actper_df;
    DOA_U8 order_num[32];
    DOA_U8 order_cnt[32];
    DOA_COMDAT *data;
} DOA_COMCTRL;

/*
 * Confirmed common 0x58-byte Model 2 player-record skeleton.
 *
 * doa:  P1 0x0054FC00, P2 0x0054FC58
 * doaa: probable P1 0x0054FBE0, P2 0x0054FC38 (derived from the same health
 *       fields moving by -0x20; apply provisionally until base fields are
 *       observed in that set).
 */
typedef struct DOA_ARCADE_PLAYER_KNOWN {
    DOA_U8 controller_type;             /* +0x00: 0 CPU, 1 human */
    DOA_U8 character_id;                /* +0x01 */
    DOA_U8 costume_id;                  /* +0x02 */
    DOA_U8 rounds_won;                  /* +0x03 */
    DOA_U8 unknown_04[0x1C];            /* +0x04 */
    DOA_U8 health;                      /* +0x20: low byte, observed 0..200 */
    DOA_U8 unknown_21[0x07];            /* +0x21 */
    DOA_U8 animation_or_action;         /* +0x28: cheat-observed selector */
    DOA_U8 unknown_29[0x2F];            /* +0x29 */
} DOA_ARCADE_PLAYER_KNOWN;

/*
 * Full field map currently used by the arcade project.  This is deliberately
 * separate from the Saturn structs above: the names bridge engine concepts,
 * while the offsets below are specific to the 0x58-byte Model 2 record.
 */
typedef struct DOA_ARCADE_PLAYER {
    DOA_U8 controller_type;             /* +0x00: 0 CPU, 1 human */
    DOA_U8 character_id;                /* +0x01 */
    DOA_U8 costume_id;                  /* +0x02 */
    DOA_U8 rounds_won;                  /* +0x03 */
    DOA_F32 x_position;                 /* +0x04: IEEE-754 float */
    DOA_F32 y_position;                 /* +0x08: IEEE-754 float */
    DOA_F32 z_position;                 /* +0x0C: IEEE-754 float */
    DOA_F32 animation_speed;            /* +0x10: IEEE-754 float */
    DOA_S32 facing_direction;           /* +0x14 */
    DOA_S32 attack_direction;           /* +0x18 */
    DOA_S32 body_direction;             /* +0x1C */
    DOA_U16 hitpoint;                   /* +0x20: current_Health*/
    DOA_U16 damage;                     /* +0x22 */
    DOA_U16 last_damage_received;       /* +0x24; persists after the impact */
    DOA_U16 damage_display;             /* +0x26; zero in captured throw */
    DOA_U8 animation_id;                /* +0x28: cheat-observed selector */
    DOA_U8 animation_aux;               /* +0x29: separate state/flag byte */
    DOA_U8 action_code;                 /* +0x2A: move ID */
    DOA_U8 action_flag;                 /* +0x2B */
    DOA_U8 action_request;              /* +0x2C: requested move ID */
    DOA_U8 action_state;                /* +0x2D */
    DOA_U8 pose_state;                  /* +0x2E */
    DOA_U8 down_state;                  /* +0x2F */
    DOA_U8 upside_down_head;            /* +0x30 */
    DOA_U8 down_direction;              /* +0x31 */
    DOA_U8 attack_point;                /* +0x32 */
    DOA_U8 attack_state;                /* +0x33 */
    DOA_U8 animation_flip;              /* +0x34 */
    DOA_U8 animation_flag;              /* +0x35 */
    DOA_U8 animation_request;           /* +0x36 */
    DOA_U8 hit_attack;                  /* +0x37 */
    DOA_U8 hit_body;                    /* +0x38 */
    DOA_U8 hit_stage;                   /* +0x39 */
    DOA_U8 guard_state;                 /* +0x3A */
    DOA_U8 jump_state;                  /* +0x3B */
    DOA_U8 jump_height;                 /* +0x3C */
    DOA_U8 jump_direction;              /* +0x3D */
    DOA_U8 beat_state;                  /* +0x3E */
    DOA_U8 sky_state;                   /* +0x3F */
    DOA_U8 down_hit;                    /* +0x40 */
    DOA_U8 action_cancel;               /* +0x41 */
    DOA_U8 grasp_state;                 /* +0x42 */
    DOA_U8 down_attack_state;           /* +0x43: (grounded_targetable) 1 on passive grounded target */
    DOA_U8 mount_state;                 /* +0x44 */
    DOA_U8 ring_out;                    /* +0x45 */
    DOA_U8 attack_height;               /* +0x46 */
    DOA_U8 ring_hit;                    /* +0x47 */
    DOA_U8 player_display;              /* +0x48 */
    DOA_U8 danger_flag;                 /* +0x49 */
    DOA_U8 direction_adjust;            /* +0x4A */
    DOA_U8 damage_number;               /* +0x4B */
    DOA_U8 side_spin;                   /* +0x4C */
    DOA_U8 hit_grasp;                   /* +0x4D */
    DOA_U8 grapple_slip;                /* +0x4E */
    DOA_U8 beat_hit_state;              /* +0x4F */
    DOA_U8 ukemi_flag;                  /* +0x50 */
    DOA_U8 danger_set;                  /* +0x51 */
    DOA_U8 combo_flag;                  /* +0x52 */
    DOA_U8 combo_count;                 /* +0x53 */
    DOA_U8 combo_start;                 /* +0x54 */
    DOA_U8 cancel_use;                  /* +0x55 */
    DOA_U8 unknown_56[2];               /* +0x56 */
} DOA_ARCADE_PLAYER;

#endif
