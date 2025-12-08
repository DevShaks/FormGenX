import argparse
from editor import EditConfig, Editor
from generator import GeneratorConfig, Generator


def main():
    parser = argparse.ArgumentParser(description="Formular generator tool")
    subparsers = parser.add_subparsers(dest="command")

    # ============================
    # EDIT MODE
    # ============================
    edit_parser = subparsers.add_parser("edit", help="Edit a template")
    edit_parser.add_argument("--template", "-t", type=str, required=True,
                             help="Template image file to edit")

    # ============================
    # GENERATE MODE
    # ============================
    gen_parser = subparsers.add_parser("generate", help="Generate filled forms")
    gen_parser.add_argument("--template", "-t", type=str, required=True,
                            help="Template image file (same as editor)")
    gen_parser.add_argument("--config", "-c", type=str, required=True,
                            help="Generator config JSON path")
    gen_parser.add_argument("--gennum", "-n", type=int, default=1,
                            help="How many samples to generate")
    gen_parser.add_argument("--outputtype", "-o", type=str, default="png",
                            help="Output file type (png, jpg, ...)")
    gen_parser.add_argument("--outputfolder", "-f", type=str, default="./output",
                            help="Output folder")
    gen_parser.add_argument("--data-path", "-d", type=str, default=None,
                            help="Optional extra data JSON")

    args = parser.parse_args()

    # ============================
    # ROUTE COMMANDS
    # ============================
    if args.command == "edit":
        cfg = EditConfig(template=args.template)
        editor = Editor(cfg)
        editor.run()

    elif args.command == "generate":
        gcfg = GeneratorConfig(
            template=args.template,
            config_path=args.config,
            gennum=args.gennum,
            outputfolder=args.outputfolder,
            outputtype=args.outputtype,
            data_path=args.data_path
        )
        gen = Generator(gcfg)
        gen.run()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
