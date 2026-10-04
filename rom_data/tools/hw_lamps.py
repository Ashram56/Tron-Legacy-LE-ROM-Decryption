"""Lamp groups (table 0x040e3acc) as lamp lists, with every code reference to each group.

Writes rom_data/io/lamp_groups.json. Run: PYTHONPATH=rom_data/tools python3 rom_data/tools/hw_lamps.py

* Table: table-of-tables entry RAM 0x36d20 = {0x040e3acc, 109, 4}: 109 u32 pointers to 0-terminated
  byte lists of lamp numbers (lamp numbers as in io/lamps.csv / the lamp test). Group 0 is the empty
  list; the OS rejects group 0 and groups > 0x6c (error_log 0x30), so groups 1..108 are usable.
* References: every BL to a group API (r0 = group, constant-propagated with hw_common.resolve_call_args),
  the leff table field +6 (leff_start 0x87ac claims that group on the leff layer 0x3c224/0x3c238),
  and the comparison with the rom_group_N tags in mpf_package/config/lights.yaml.
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rom import u8, u16, u32, hx, find_bl_callers
from hw_common import resolve_call_args, func_of, REPO

OUT = os.path.join(REPO, 'rom_data', 'io')
GT, GN, GS = u32(0x36d20), u32(0x36d24), u32(0x36d28)
LT, LN = u32(0x36cf0), u32(0x36cf4)

# group API: addr -> (name, what it does). r0 is the group in every one (code: each indexes 0x040e3acc
# with r0 after the 1..0x6c range check). "planes" = the 2-plane lamp image (10 bytes per plane);
# "mask" = the 10-byte ownership mask of a layer.
GROUP_API = {
    0x8f78: ('lampgroup_count', 'number of lamps in the group'),
    0x8fdc: ('lampgroup_member', 'lamp number at index i'),
    0x9068: ('lampgroup_off', 'all members off in an image'),
    0x90d8: ('lampgroup_bit_clear', 'clear members from a layer mask'),
    0x9140: ('lampgroup_off_unmask', 'members off in an image and cleared from a mask'),
    0x9200: ('lampgroup_on', 'all members on in an image'),
    0x9270: ('lampgroup_bit_set', 'add members to a layer mask'),
    0x92d8: ('lampgroup_on_unmask', 'members on in an image and cleared from a mask'),
    0x9398: ('lampgroup_toggle', 'toggle all members in an image'),
    0x9408: ('lampgroup_bit_toggle', 'toggle members in a mask'),
    0x9470: ('lampgroup_all_on', 'true when every member is on'),
    0x9500: ('lampgroup_all_bits', 'true when every member bit is set in a mask'),
    0x9588: ('lampgroup_rotate_b', 'rotate member states by one place (image); direction opposite to 0x987c (inferred)'),
    0x9750: ('lampgroup_bit_rotate_b', 'rotate member bits by one place (mask)'),
    0x987c: ('lampgroup_rotate', 'rotate member states by one place (image), the last wraps to the first'),
    0x9a70: ('lampgroup_bit_rotate', 'rotate member bits by one place (mask)'),
    0x9b9c: ('lampgroup_fill_rev', 'turn on the lamp before the first lit member (fills from the end); returns 1 at the first member'),
    0x9c54: ('lampgroup_bit_fill_rev', 'mask version of 0x9b9c'),
    0x9d00: ('lampgroup_fill', 'turn on the first unlit member; returns 1 when the group is full'),
    0x9db0: ('lampgroup_bit_fill', 'mask version of 0x9d00'),
    0x9e54: ('lampgroup_drain_rev', 'turn off the lamp before the first unlit member; returns 1 at the first member'),
    0x9f0c: ('lampgroup_bit_drain_rev', 'mask version of 0x9e54'),
    0x9fb8: ('lampgroup_drain', 'turn off the first lit member; returns 1 when the group is empty'),
    0xa068: ('lampgroup_bit_drain', 'mask version of 0x9fb8'),
    0xa10c: ('lampgroup_overlap', 'true when two groups share a lamp (leff_start conflict test)'),
    0x7d9c: ('lamp_layer_create', 'new lamp layer owning the group (0 = no group), r1 = priority'),
}

# Names from the member lists (tag inferred). Usage is in "references".
NAMES = {
    1: 'all_playfield_lamps_sweep_order', 2: 'all_playfield_lamps_less_shoot_again_outlanes_clu_c_eject_extra_ball',
    3: 'checker_a (every other lamp of group 1)', 4: 'checker_b (the other half of group 1)',
    5: 'outlanes_and_clu_letters', 6: 'center_inserts_10', 7: 'tron_letters_right_to_left',
    8: 'double_scoring_bumpers_spinners', 9: 'eject_awards', 10: 'zuse_letters', 11: 'left_orbit_inserts',
    12: 'left_ramp_inserts', 13: 'left_inner_loop_inserts_with_advance_quorra', 14: 'right_inner_loop_inserts',
    15: 'right_ramp_inserts', 16: 'bumper_lamps', 17: 'right_orbit_inserts',
    18: 'shoot_again_eject_clu_flynns_arcade_recognizer_bank', 19: 'recognizer_positions',
    20: 'disc_lamps_and_tron_letters', 21: 'clu_and_light_cycle_lamps', 22: 'quorra_lamps',
    23: 'arrows_and_recognizer_lamps', 24: 'outlanes', 25: 'zuse_portal_and_bumper_lamps', 26: 'center_gem',
    27: 'shoot_again_and_eject_extra_ball', 28: 'left_ramp_inserts', 29: 'right_ramp_inserts',
    30: 'flynns_arcade', 31: 'tron_letters', 32: 'double_scoring_bumpers_spinners', 33: 'bumper_lamps',
    34: 'bumper_lamps', 35: 'apron_lamps (start buttons, shoot again, eject extra ball, outlanes)',
    36: 'inner_loop_inserts', 37: 'arrows_inner_eject_lamps', 38: 'apron_lamps', 39: 'light_cycle_shot_lamps',
    40: 'light_cycle_shot_lamps', 41: 'apron_lamps', 42: 'clu_shot_lamps', 43: 'clu_letters',
    44: 'left_orbit_clu', 45: 'left_inner_loop_clu', 46: 'right_orbit_clu', 47: 'eject_clu',
    48: 'right_inner_loop_inserts', 49: 'outlanes_and_clu_letters', 50: 'clu_letters', 51: 'outlanes',
    52: 'recognizer_positions', 53: 'zuse_letters', 54: 'zuse_letters', 55: 'arrows_bumpers_recognizer_bank',
    56: 'zuse_letters', 57: 'zuse_letters', 58: 'zuse_letters', 59: 'double_scoring_bumpers_spinners',
    60: 'center_inserts_9 (no portal)', 61: 'center_inserts_10', 62: 'left_inner_loop_inserts_with_advance_quorra',
    63: 'left_loop_arrow', 64: 'left_loop_arrow', 65: 'left_ramp_arrow', 66: 'left_inner_loop_arrow',
    67: 'right_inner_loop_arrow', 68: 'right_ramp_arrow', 69: 'right_loop_arrow', 70: 'left_loop_arrow',
    71: 'left_ramp_arrow', 72: 'left_inner_loop_arrow', 73: 'right_inner_loop_arrow', 74: 'right_ramp_arrow',
    75: 'right_loop_arrow', 76: 'clu_letters', 77: 'eject_awards_reversed', 78: 'right_inner_loop_inserts',
    79: 'clu_shot_lamps_and_clu_letters', 80: 'zuse_letters', 81: 'left_inner_loop_inserts_with_advance_quorra',
    82: 'disc_shot_lamps', 83: 'light_cycle_shot_lamps', 84: 'recognizer_bank_and_positions',
    85: 'tron_letters', 86: 'eject_portal', 87: 'apron_lamps', 88: 'all_shot_inserts_left_to_right',
    89: 'left_orbit_inserts', 90: 'left_ramp_inserts', 91: 'left_inner_loop_inserts_with_advance_quorra',
    92: 'right_inner_loop_inserts', 93: 'right_ramp_inserts', 94: 'right_orbit_inserts',
    95: 'center_inserts_10', 96: 'recognizer_3_bank', 97: 'apron_lamps', 98: 'left_orbit_disc',
    99: 'left_ramp_disc', 100: 'left_inner_loop_disc', 101: 'right_inner_loop_disc', 102: 'right_ramp_disc',
    103: 'right_orbit_disc', 104: 'recognizer_3_bank', 105: 'apron_lamps', 106: 'apron_lamps',
    107: 'apron_lamps', 108: 'apron_lamps',
}


# ROM tables of group ids read by code (layout read from the code that indexes them; see code_leffs.json)
# (table, count, stride, offset of the u16 group, user)
TABLE_REFS = [
    (0x040d26c0, 8, 20, 4, 'leffs 44/45/55 and disc multiball code: {u32 shot mask, u16 group}'),
    (0x040d22dc, 4, 8, 4, 'leff 78 CLU shot lamps: {u32 clu_shots mask, u16 group}'),
    (0x040d294c, 6, 8, 0, 'leff 157 roving arrow: group per ff_pos'),
    (0x040d2324, 6, 12, 8, 'leff 159 combo arrows: {u32 mask, u32, u16 group}'),
    (0x040d6e18, 7, 16, 0, 'leff 166 portal multiball shots: {u16 group, .., u8* count}'),
    (0x040d2f00, 15, 2, 0, 'leff 1 attract: groups filled then rotated (lampgroup_rotate 0x987c)'),
    (0x040d2f38, 8, 4, 0, 'leff 1 attract group_flash_task: {u16 group, u16 tube show}'),
]


def members(g):
    p = u32(GT + 4 * g)
    out = []
    while u8(p):
        out.append(u8(p))
        p += 1
    return p, out


def lamp_names():
    return {int(r['lamp']): r['name'] for r in csv.DictReader(open(os.path.join(REPO, 'io', 'lamps.csv')))}


def light_names():
    """lamp number -> (mpf light name, tags) from lights.yaml, read as text (no YAML edit)"""
    out, cur = {}, None
    rx = re.compile(r'^  (l_\w+):')
    for line in open(os.path.join(REPO, 'mpf_package', 'config', 'lights.yaml')):
        m = rx.match(line)
        if m:
            cur = [m.group(1), None, '']
            continue
        if cur and line.strip().startswith('number:'):
            v = line.split(':')[1].split('#')[0].strip()
            if v.isdigit():
                cur[1] = int(v)
                out[cur[1]] = cur
        elif cur and line.strip().startswith('tags:'):
            cur[2] = line.split(':', 1)[1].strip()
    return {n: (c[0], c[2]) for n, c in out.items()}


def main():
    assert GS == 4 and GN == 109, (GN, GS)
    names = lamp_names()
    lights = light_names()
    refs = {g: [] for g in range(GN)}
    unresolved = []
    for api, (aname, _) in sorted(GROUP_API.items()):
        for pc, link in sorted(find_bl_callers(api)):
            regs, _, _ = resolve_call_args(pc, nstack=0)
            fs, fn = func_of(pc)
            gs = [regs.get(0)] + ([regs.get(1)] if api == 0xa10c else [])
            for k, g in enumerate(gs):
                rec = {'site': hx(pc), 'caller_fn': hx(fs) if fs is not None else '', 'caller_name': fn or '',
                       'api': aname, 'api_addr': hx(api), 'arg': 'r%d' % k, 'tag': 'code'}
                if api == 0x7d9c:
                    rec['priority'] = regs.get(1)
                if g is None:
                    unresolved.append(rec)
                    continue
                g &= 0xffff
                if g == 0 and api == 0x7d9c:
                    continue  # layer without a group
                if 0 <= g < GN:
                    refs[g].append(rec)
                else:
                    rec['group'] = g
                    unresolved.append(dict(rec, note='constant out of range'))
    for t, n, stride, off, user in TABLE_REFS:
        for k in range(n):
            g = u16(t + k * stride + off)
            if 0 < g < GN:
                refs[g].append({'site': hx(t + k * stride + off), 'api': 'rom_table', 'table': hx(t), 'index': k,
                                'user': user, 'tag': 'code'})
    # groups passed to the parametric group leffs (40/103/122/143 read a u16 group at task+0x30)
    from hw_leffs import leff_start_sites
    for pc, (fs, fname), lid, param in leff_start_sites():
        if lid is not None and (lid & 0xffff) in (40, 103, 122, 143) and isinstance(param, int) and 0 < param < GN:
            refs[param].append({'site': hx(pc), 'caller_fn': hx(fs) if fs else '', 'caller_name': fname or '',
                                'api': 'leff_start param (task+0x30)', 'leff': lid & 0xffff, 'tag': 'code'})
    for i in range(1, LN):
        g = u16(LT + 12 * i + 6)
        if g:
            refs[g].append({'site': hx(LT + 12 * i + 6), 'api': 'leff_table_lamp_group', 'leff': i,
                            'leff_fn': hx(u32(LT + 12 * i)),
                            'note': 'leff_start 0x87ac: claims the group on the leff layer (lampgroup_off on image 0x3c224, '
                                    'lampgroup_bit_set on mask 0x3c238); the leff task reads it with 0x8d10', 'tag': 'code'})
    # lights.yaml rom_group tags
    tagged = {}
    for n, (lname, tags) in lights.items():
        for t in tags.split():
            m = re.match(r'rom_group_(\d+)', t)
            if m:
                tagged.setdefault(int(m.group(1)), []).append(n)
    groups = []
    for g in range(GN):
        p0, mem = members(g)
        cmp = None
        if g in tagged:
            a, b = sorted(tagged[g]), sorted(mem)
            cmp = {'lights_yaml_lamps': a, 'match': a == b,
                   'missing_in_yaml': sorted(set(b) - set(a)), 'extra_in_yaml': sorted(set(a) - set(b))}
        groups.append({
            'group': g, 'list_addr': hx(u32(GT + 4 * g)), 'entry_addr': hx(GT + 4 * g),
            'count': len(mem), 'lamps': mem,
            'lamp_names': [names.get(n, '?') for n in mem],
            'mpf_lights': [lights.get(n, ('',))[0] for n in mem],
            'tag': 'code',
            'name': NAMES.get(g, 'empty' if not mem else ''), 'name_tag': 'inferred',
            'same_lamps_as': [h for h in range(1, GN) if h != g and sorted(members(h)[1]) == sorted(mem) and mem],
            'same_order_as': [h for h in range(1, GN) if h != g and members(h)[1] == mem and mem],
            'references': refs[g],
            'lights_yaml_rom_group': cmp,
        })
    doc = {
        'source': 'table 0x040e3acc (table-of-tables RAM 0x36d20: count %d, record size %d); lists are 0-terminated '
                  'lamp numbers; groups 1..0x6c are valid (range check in every group API, error_log 0x30)' % (GN, GS),
        'group_api': {hx(a): {'name': n, 'meaning': m, 'tag': 'code'} for a, (n, m) in sorted(GROUP_API.items())},
        'groups': groups,
        'unresolved_references': unresolved,
        'notes': [
            'Group 0 is the empty list at 0x040e37f8.',
            'Several groups hold the same lamps; same_lamps_as / same_order_as list them. Order matters for the '
            'fill/drain/rotate APIs (they walk the list in order).',
            'unresolved_references: the group is a variable (task+0x30 parameter, a table, or a loop); see '
            'code_leffs.json for the leff ones.',
        ],
    }
    with open(os.path.join(OUT, 'lamp_groups.json'), 'w') as f:
        json.dump(doc, f, indent=1)
    nref = sum(len(v) for v in refs.values())
    print('groups', GN, 'refs', nref, 'unresolved', len(unresolved),
          'unreferenced', [g for g in range(1, GN) if not refs[g]])
    for g, c in sorted(tagged.items()):
        print('rom_group_%d' % g, groups[g]['lights_yaml_rom_group'])


if __name__ == '__main__':
    main()
