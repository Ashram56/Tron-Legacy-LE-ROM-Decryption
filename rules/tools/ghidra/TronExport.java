// Post-analysis: re-apply signatures and decompile every function to one C file.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;
import java.nio.file.*;

public class TronExport extends GhidraScript {
  public void run() throws Exception {
    String out = getScriptArgs().length > 0 ? getScriptArgs()[0] : "/home/claude/work/gh/out.c";
    DecompInterface di = new DecompInterface();
    DecompileOptions o = new DecompileOptions();
    di.setOptions(o);
    di.toggleCCode(true); di.toggleSyntaxTree(false);
    di.openProgram(currentProgram);
    try (PrintWriter w = new PrintWriter(new FileWriter(out))) {
      FunctionIterator it = currentProgram.getListing().getFunctions(true);
      int n = 0;
      while (it.hasNext()) {
        Function f = it.next();
        DecompileResults r = di.decompileFunction(f, 90, monitor);
        w.println("// ==== " + String.format("%08x", f.getEntryPoint().getOffset()) + " " + f.getName());
        if (r != null && r.decompileCompleted()) w.println(r.getDecompiledFunction().getC());
        else w.println("/* decompile failed: " + (r == null ? "null" : r.getErrorMessage()) + " */\n");
        n++;
      }
      println("decompiled " + n);
    }
  }
}
