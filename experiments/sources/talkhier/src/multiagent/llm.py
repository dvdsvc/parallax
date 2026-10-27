from langchain_openai import ChatOpenAI

class LLM:

    def __init__(self, config):
        self.config = config
        self.openai_api_key = str(config["KEYS"][f"OPENAI_API_KEY"])
        self.base_url = str(config["KEYS"][f"OPENAI_ENDPOINT"])
        assert not "***********" in self.openai_api_key, "Error: Please input keys."
        self.loadLLM()


    def loadLLM(self):
        self.llm = ChatOpenAI(
            model=self.config["LLM"].get("model", "qwen3.7-flash"),
            api_key=self.openai_api_key,
            base_url=self.base_url,
            temperature=float(self.config["LLM"]["temperature"]),
            max_completion_tokens=self.config["LLM"].getint("max_completion_tokens", fallback=16384),
            extra_body={
                "enable_thinking": self.config["LLM"].getboolean("enable_thinking", fallback=True),
                "thinking_budget": self.config["LLM"].getint("thinking_budget", fallback=8192),
            },
            timeout=self.config["LLM"].getfloat("request_timeout", fallback=900),
            max_retries=self.config["LLM"].getint("max_retries", fallback=2),
        )
