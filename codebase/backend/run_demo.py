from learning_agent import LearningOSAgent



def main() -> None:
    agent = LearningOSAgent()

    print("=== General question ===")
    print(agent.ask("Build slice là gì trong product management?").to_dict()["answer"])

    print("\n=== Course question before source ===")
    print(agent.ask("Trong slide Day05, build slice là gì?").to_dict()["answer"])

    print("\n=== Load source ===")
    source = agent.load_source(
        "Build slice: một user, một task, một AI decision, một output. "
        "Thin SPEC chỉ cần đủ để build. 4 paths gồm happy, low-confidence, failure, correction."
    )
    print({"title": source.title, "chunks": len(source.chunks)})

    print("\n=== Course question after source ===")
    print(agent.ask("Trong slide Day05, build slice là gì?").to_dict()["answer"])

    print("\n=== Ops refusal ===")
    print(agent.ask("Deadline nộp repo mấy giờ?").to_dict()["answer"])


if __name__ == "__main__":
    main()

