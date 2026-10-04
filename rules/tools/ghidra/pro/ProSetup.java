// Pre-analysis: memory map, function seeds, names and signatures.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.data.*;
import ghidra.app.cmd.disassemble.ArmDisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public class ProSetup extends GhidraScript {
  static String W = "/home/claude/work/ghp/";
  MemoryBlock blk(String n, long a, byte[] rom, int off, int len, boolean x, boolean w) throws Exception {
    Memory mem = currentProgram.getMemory();
    byte[] b = new byte[len];
    int c = Math.max(0, Math.min(len, rom.length - off));
    System.arraycopy(rom, off, b, 0, c);
    MemoryBlock m = mem.createInitializedBlock(n, toAddr(a), new ByteArrayInputStream(b), len, monitor, false);
    m.setRead(true); m.setWrite(w); m.setExecute(x);
    return m;
  }
  public void run() throws Exception {
    byte[] rom = Files.readAllBytes(Path.of("/mnt/project-files/tron/pro/TRN174VP.BIN"));
    Memory mem = currentProgram.getMemory();
    for (MemoryBlock b : mem.getBlocks()) { b.setWrite(false); b.setExecute(false); b.setName("FLASH"); }
    blk("OS", 0, rom, 0, 0x2fa00, true, false);
    blk("RAM", 0x2fa00, rom, 0x2fa00, 0xd0600, false, true);
    blk("GAME", 0x01000000, rom, 0x40000, 0x100000, true, false);
    MemoryBlock nv = mem.createUninitializedBlock("NVRAM", toAddr(0x02100000), 0x20000, false); nv.setWrite(true);
    MemoryBlock io = mem.createUninitializedBlock("IO", toAddr(0x02400000), 0x1000, false); io.setWrite(true); io.setVolatile(true);
    // signatures
    Map<Long,String[]> sig = new HashMap<>();
    for (String l : Files.readAllLines(Path.of(W + "sigs.tsv"))) {
      if (l.isBlank() || l.startsWith("#")) continue;
      String[] p = l.split("\t");
      sig.put(Long.parseLong(p[0], 16), p);
    }
    SymbolTable st = currentProgram.getSymbolTable();
    Listing lst = currentProgram.getListing();
    int made = 0;
    for (String l : Files.readAllLines(Path.of(W + System.getProperty("tron.seeds","seeds_final.tsv")))) {
      String[] p = l.split("\t", -1);
      long a = Long.parseLong(p[0], 16);
      Address ad = toAddr(a);
      if (!mem.contains(ad)) continue;
      new ArmDisassembleCommand(ad, null, false).applyTo(currentProgram, monitor);
      Function f = lst.getFunctionAt(ad);
      if (f == null) { new CreateFunctionCmd(ad).applyTo(currentProgram, monitor); f = lst.getFunctionAt(ad); }
      if (f == null) continue;
      made++;
      if (p.length > 1 && !p[1].isEmpty()) f.setName(p[1], SourceType.USER_DEFINED);
    }
    for (Map.Entry<Long,String[]> e : sig.entrySet()) {
      Address ad = toAddr(e.getKey());
      new ArmDisassembleCommand(ad, null, false).applyTo(currentProgram, monitor);
      Function f = lst.getFunctionAt(ad);
      if (f == null) { new CreateFunctionCmd(ad).applyTo(currentProgram, monitor); f = lst.getFunctionAt(ad); }
      if (f == null) { println("no func " + Long.toHexString(e.getKey())); continue; }
      applySig(f, e.getValue()[1]);
    }
    Path rp = Path.of(W + "ram_symbols.tsv");
    if (Files.exists(rp)) for (String l : Files.readAllLines(rp)) {
      if (l.isBlank() || l.startsWith("#")) continue;
      String[] p = l.split("\t");
      try { st.createLabel(toAddr(Long.parseLong(p[0].replace("0x",""), 16)), p[1], SourceType.USER_DEFINED); } catch (Exception ex) { println("label fail " + l); }
    }
    println("functions seeded: " + made);
  }
  DataType dt(String t) {
    t = t.trim();
    DataTypeManager dm = currentProgram.getDataTypeManager();
    boolean ptr = t.endsWith("*");
    String b = ptr ? t.substring(0, t.length()-1).trim() : t;
    DataType d;
    switch (b) {
      case "int": d = IntegerDataType.dataType; break;
      case "uint": case "unsigned int": d = UnsignedIntegerDataType.dataType; break;
      case "short": d = ShortDataType.dataType; break;
      case "ushort": d = UnsignedShortDataType.dataType; break;
      case "char": d = CharDataType.dataType; break;
      case "uchar": case "byte": case "bool": d = ByteDataType.dataType; break;
      case "void": d = VoidDataType.dataType; break;
      default: d = Undefined4DataType.dataType;
    }
    return ptr ? new PointerDataType(d) : d;
  }
  void applySig(Function f, String s) throws Exception {
    // "ret name(type a, type b, ...)"
    int lp = s.indexOf('('), rp = s.lastIndexOf(')');
    String head = s.substring(0, lp).trim();
    int sp = Math.max(head.lastIndexOf(' '), head.lastIndexOf('*'));
    String ret = head.substring(0, sp+1).trim(); String name = head.substring(sp+1).trim();
    String args = s.substring(lp+1, rp).trim();
    List<ParameterImpl> ps = new ArrayList<>();
    boolean varargs = false;
    if (!args.isEmpty() && !args.equals("void")) {
      int i = 0;
      for (String a : args.split(",")) {
        a = a.trim();
        if (a.equals("...")) { varargs = true; continue; }
        int k = Math.max(a.lastIndexOf(' '), a.lastIndexOf('*'));
        String ty = k > 0 ? a.substring(0, k+1) : a; String pn = k > 0 ? a.substring(k+1).trim() : "p" + i;
        if (pn.isEmpty()) pn = "p" + i;
        ps.add(new ParameterImpl(pn, dt(ty), currentProgram));
        i++;
      }
    }
    f.setName(name, SourceType.USER_DEFINED);
    f.updateFunction("__stdcall", new ReturnParameterImpl(dt(ret), currentProgram), ps,
        Function.FunctionUpdateType.DYNAMIC_STORAGE_ALL_PARAMS, true, SourceType.USER_DEFINED);
    f.setVarArgs(varargs);
  }
}
