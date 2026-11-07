import type { Language } from "../types";

export const TEMPLATES: Record<Language, string> = {
  python: `import sys

def main():
    data = sys.stdin.read().strip().split()
    # Напишите решение здесь

if __name__ == "__main__":
    main()
`,
  cpp: `#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    // Напишите решение здесь
    return 0;
}
`,
  java: `import java.util.*;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        // Напишите решение здесь
    }
}
`,
  javascript: `const fs = require("fs");
const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/);

function main() {
  // Напишите решение здесь
}

main();
`,
};

export const MONACO_LANGUAGE: Record<Language, string> = {
  python: "python",
  cpp: "cpp",
  java: "java",
  javascript: "javascript",
};

export function isTemplate(code: string) {
  return Object.values(TEMPLATES).includes(code);
}
