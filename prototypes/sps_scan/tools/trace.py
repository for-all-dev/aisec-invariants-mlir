from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
import sys

BASE=0x1000; STACK=0x80000; TABLE=0x40000

def load(objfile, symname):
    f=open(objfile,'rb'); e=ELFFile(f)
    text=e.get_section_by_name('.text')
    code=text.data()
    sym=e.get_section_by_name('.symtab').get_symbol_by_name(symname)[0]
    return code, sym['st_value']

def run(objfile, symname, secret):
    code, off = load(objfile, symname)
    mu=Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    mu.mem_map(BASE,0x10000); mu.mem_map(STACK-0x10000,0x20000); mu.mem_map(TABLE,0x1000)
    mu.mem_write(BASE, code)
    for i in range(16): mu.mem_write(TABLE+4*i, (0xAA00+i).to_bytes(4,'little'))
    mu.reg_write(UC_ARM_REG_SP, STACK)
    mu.reg_write(UC_ARM_REG_R0, TABLE)      # table*
    mu.reg_write(UC_ARM_REG_R1, secret)     # secret_index
    RET=BASE+0x8000
    mu.reg_write(UC_ARM_REG_LR, RET|1)      # return sentinel
    reads=[]; ic=[0]
    mu.hook_add(UC_HOOK_MEM_READ, lambda u,a,addr,sz,val,d: reads.append(addr))
    mu.hook_add(UC_HOOK_CODE, lambda u,addr,sz,d: ic.__setitem__(0, ic[0]+1))
    try: mu.emu_start((BASE+off)|1, RET|1, count=20000)
    except UcError: pass
    return ic[0], [r for r in reads if TABLE <= r < TABLE+64]

for obj,sym in [("si_bad.o","secret_embedding_index_bad"),("si_fixed.o","secret_embedding_index_fixed")]:
    print(f"\n=== {sym} (thumbv7m / cortex-m3) ===")
    sig=set()
    for s in (0,1,7,15):
        ic,rd = run(obj,sym,s)
        offs = sorted({(r-TABLE)//4 for r in rd})
        sig.add((ic,tuple(offs)))
        print(f"  secret={s:2d}  instrs={ic:4d}  table words read={offs}")
    print(f"  --> distinct (instr-count, address-set) signatures across secrets: {len(sig)}"
          f"  {'LEAK: address trace depends on secret' if len(sig)>1 else 'no secret-dependent trace'}")
