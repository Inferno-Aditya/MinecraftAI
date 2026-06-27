import re
import os
import json
from typing import Dict, Any, List

class IntentClassifier:
    """
    Classifier to determine intent category for Minecraft AI queries.
    Uses rule-based classification with weighted confidence scoring,
    alias/synonym resolution, and semantic candidate tool ranking.
    """
    def __init__(self):
        # Load configuration
        config_path = os.path.join(os.path.dirname(__file__), "intent_classifier_config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except Exception as e:
            # Fail-safe default config if file is missing
            self.config = {}

        self.threshold = self.config.get("confidence_threshold", 0.45)
        self.fallback_intent = self.config.get("fallback_intent", "KNOWLEDGE")
        self.aliases = self.config.get("aliases", {})
        self.spatial_keywords = self.config.get("spatial_keywords", [])
        self.mobs_dict = self.config.get("mobs", {})
        self.structures = self.config.get("structures", [])
        self.blocks = self.config.get("blocks", [])
        self.items = self.config.get("items", [])
        self.action_verbs = self.config.get("action_verbs", [])
        self.intent_rules = self.config.get("intent_rules", {})
        self.category_tool_weights = self.config.get("category_tool_weights", {})
        self.tool_keyword_rules = self.config.get("tool_keyword_rules", {})

    def _match_word_or_phrase(self, term: str, message: str) -> bool:
        """Helper to match a word or multi-word phrase with boundary checks, supporting regular plurals."""
        # Using word boundaries, allowing spaces in multi-word phrases, and optional plural suffix (s or es)
        pattern = r"\b" + re.escape(term) + r"(s|es)?\b"
        return re.search(pattern, message, re.IGNORECASE) is not None

    def _match_any_alias(self, canonical_term: str, message: str) -> bool:
        """Check if canonical term or any of its synonyms match in the message."""
        if self._match_word_or_phrase(canonical_term, message):
            return True
        synonyms = self.aliases.get(canonical_term, [])
        for syn in synonyms:
            if self._match_word_or_phrase(syn, message):
                return True
        return False

    def _detect_terms(self, term_list: List[str], message: str) -> List[str]:
        """Detect and return canonical terms matching the message."""
        detected = []
        for term in term_list:
            if self._match_any_alias(term, message):
                detected.append(term)
        return list(set(detected))

    def classify(self, message: str) -> Dict[str, Any]:
        """
        Classifies a user message and returns metadata with explainability diagnostics.
        """
        msg = message.lower()

        # 1. Explainability and entity tracking
        contributing_factors = {
            "spatial_keywords": [],
            "mobs": [],
            "structures": [],
            "blocks": [],
            "items": [],
            "action_verbs": [],
            "matched_patterns": {}
        }

        # Detect spatial keywords
        matched_spatial = [sk for sk in self.spatial_keywords if self._match_word_or_phrase(sk, msg)]
        contributing_factors["spatial_keywords"] = matched_spatial

        # Detect action verbs
        matched_verbs = [av for av in self.action_verbs if self._match_word_or_phrase(av, msg)]
        contributing_factors["action_verbs"] = matched_verbs

        # Detect Mobs
        matched_mobs = []
        for cat, mobs in self.mobs_dict.items():
            for mob in mobs:
                if self._match_any_alias(mob, msg):
                    matched_mobs.append(mob)
        matched_mobs = list(set(matched_mobs))
        contributing_factors["mobs"] = matched_mobs

        # Detect Structures, Blocks, Items
        matched_structures = self._detect_terms(self.structures, msg)
        contributing_factors["structures"] = matched_structures

        matched_blocks = self._detect_terms(self.blocks, msg)
        contributing_factors["blocks"] = matched_blocks

        matched_items = self._detect_terms(self.items, msg)
        contributing_factors["items"] = matched_items

        # 2. Intent score calculation
        confidences = {intent: 0.0 for intent in self.intent_rules.keys()}

        has_spatial = len(matched_spatial) > 0
        has_mob = len(matched_mobs) > 0
        has_structure = len(matched_structures) > 0
        has_block = len(matched_blocks) > 0
        has_item = len(matched_items) > 0
        has_verb = len(matched_verbs) > 0

        # Spatial contributions
        if has_spatial:
            confidences["ENVIRONMENT"] += 0.4
            confidences["KNOWLEDGE"] += 0.05
            confidences["PLAYER"] += 0.02
            confidences["MEMORY"] += 0.1

        # Structure contributions
        if has_structure:
            confidences["ENVIRONMENT"] += 0.56
            confidences["KNOWLEDGE"] += 0.16
            confidences["PLAYER"] += 0.02

        # Mob contributions
        if has_mob:
            confidences["ENVIRONMENT"] += 0.5
            confidences["KNOWLEDGE"] += 0.2
            confidences["PLAYER"] += 0.05

        # Block contributions
        if has_block:
            confidences["ENVIRONMENT"] += 0.5
            confidences["KNOWLEDGE"] += 0.2
            confidences["PLAYER"] += 0.05

        # Item contributions
        if has_item:
            confidences["PLAYER"] += 0.4
            confidences["KNOWLEDGE"] += 0.2
            confidences["HYBRID"] += 0.2

        # Action verb contributions
        if has_verb:
            confidences["KNOWLEDGE"] += 0.1
            confidences["PLAYER"] += 0.1
            confidences["ENVIRONMENT"] += 0.1
            confidences["HYBRID"] += 0.1
            confidences["MEMORY"] += 0.1

        # Rule/pattern matches
        for intent, rule in self.intent_rules.items():
            matched_pats = []
            for pat in rule.get("patterns", []):
                # Pattern can be exact phrase match using word boundaries
                if re.search(r"\b" + re.escape(pat) + r"\b", msg, re.IGNORECASE):
                    matched_pats.append(pat)
            if matched_pats:
                weight = rule.get("weight", 1.0)
                confidences[intent] += 0.6 * len(matched_pats) * weight
                contributing_factors["matched_patterns"][intent] = matched_pats

        # Baseline default check
        if not has_spatial and not has_mob and not has_structure and not has_block and not has_item:
            confidences["KNOWLEDGE"] += 0.4

        # Clip and round confidence scores
        for intent in list(confidences.keys()):
            confidences[intent] = round(min(1.0, max(0.0, confidences[intent])), 2)

        # Include WORLD_SEARCH alias for ENVIRONMENT for compatibility/diagnostics
        confidences["WORLD_SEARCH"] = confidences["ENVIRONMENT"]

        # 3. Intent Selection and Fallback Threshold
        primary_intents = ["KNOWLEDGE", "PLAYER", "ENVIRONMENT", "MEMORY", "TOOL", "HYBRID"]
        sorted_intents = sorted([(intent, confidences[intent]) for intent in primary_intents], key=lambda x: x[1], reverse=True)
        highest_intent, highest_score = sorted_intents[0]

        is_uncertain = False
        final_intent = highest_intent
        if highest_score < self.threshold:
            is_uncertain = True
            final_intent = self.fallback_intent

        # Determine strategy requirements
        if final_intent == "HYBRID":
            required_context = ["player_context", "environment_snapshot"]
            required_memory = True
            tool_execution_expected = True
        elif final_intent == "TOOL":
            required_context = ["player_context", "environment_snapshot"]
            required_memory = True
            tool_execution_expected = True
        elif final_intent == "MEMORY":
            required_context = ["player_context"]
            required_memory = True
            tool_execution_expected = True
        elif final_intent == "ENVIRONMENT":
            required_context = ["player_context", "environment_snapshot"]
            required_memory = False
            tool_execution_expected = True
        elif final_intent == "PLAYER":
            required_context = ["player_context"]
            required_memory = False
            tool_execution_expected = True
        else: # KNOWLEDGE
            required_context = []
            required_memory = False
            tool_execution_expected = False

        # 4. Candidate Tool Ranking
        tool_scores = {}
        try:
            from tools.registry import registry
            all_tools = list(registry.list_tools().keys())
        except Exception:
            all_tools = [
                "get_player_status", "get_held_item", "get_equipment", "get_inventory",
                "get_weather", "get_time", "get_light_level", "get_nearby_blocks",
                "scan_area", "find_nearest", "get_nearby_entities", "get_biome",
                "save_location", "load_location", "list_locations", "save_note",
                "get_player_info", "get_health", "get_food", "get_dimension", "get_world_time"
            ]

        for t in all_tools:
            tool_scores[t] = 0.0

        # Category mapping boosts
        if has_mob:
            for t, w in self.category_tool_weights.get("mobs", {}).items():
                if t in tool_scores:
                    tool_scores[t] = max(tool_scores[t], w)
        if has_structure:
            for t, w in self.category_tool_weights.get("structures", {}).items():
                if t in tool_scores:
                    tool_scores[t] = max(tool_scores[t], w)
        if has_block:
            for t, w in self.category_tool_weights.get("blocks", {}).items():
                if t in tool_scores:
                    tool_scores[t] = max(tool_scores[t], w)
        if has_item:
            for t, w in self.category_tool_weights.get("items", {}).items():
                if t in tool_scores:
                    tool_scores[t] = max(tool_scores[t], w)
        if has_spatial:
            for t, w in self.category_tool_weights.get("spatial", {}).items():
                if t in tool_scores:
                    tool_scores[t] = max(tool_scores[t], w)

        # Keyword mapping boosts
        for t, keywords in self.tool_keyword_rules.items():
            if t not in tool_scores:
                continue
            matched_kws = []
            for kw in keywords:
                if self._match_any_alias(kw, msg):
                    matched_kws.append(kw)
            if matched_kws:
                tool_scores[t] = min(1.0, tool_scores[t] + 0.4 * len(matched_kws))

        # Filter tools relevant to the resolved intent
        player_tools = [
            "get_player_status", "get_held_item", "get_equipment", "get_inventory",
            "get_player_info", "get_health", "get_food", "get_dimension"
        ]
        env_tools = [
            "get_biome", "get_weather", "get_time", "get_light_level",
            "get_nearby_blocks", "scan_area", "find_nearest", "get_nearby_entities",
            "get_world_time", "get_dimension"
        ]
        mem_tools = ["save_location", "load_location", "list_locations", "save_note"]

        allowed_tools = None
        if final_intent == "PLAYER":
            allowed_tools = player_tools
        elif final_intent == "ENVIRONMENT":
            allowed_tools = env_tools
        elif final_intent == "MEMORY":
            allowed_tools = mem_tools
        elif final_intent == "KNOWLEDGE":
            allowed_tools = []

        if allowed_tools is not None:
            filtered_scores = {t: score for t, score in tool_scores.items() if t in allowed_tools}
        else:
            filtered_scores = tool_scores

        ranked_tools = sorted([(t, round(score, 2)) for t, score in filtered_scores.items() if score > 0.0], key=lambda x: x[1], reverse=True)

        # Ensure tools populated if execution expected
        if not ranked_tools and final_intent != "KNOWLEDGE":
            fallback_set = allowed_tools if allowed_tools is not None else all_tools
            ranked_tools = [(t, 0.5) for t in fallback_set]

        required_tools = [t for t, _ in ranked_tools]
        tool_confidences = {t: score for t, score in ranked_tools}

        return {
            "intent": final_intent,
            "required_context": required_context,
            "required_memory": required_memory,
            "required_tools": required_tools,
            "tool_confidences": tool_confidences,
            "tool_execution_expected": tool_execution_expected,
            "diagnostics": {
                "detected_mobs": matched_mobs,
                "detected_structures": matched_structures,
                "detected_blocks": matched_blocks,
                "detected_items": matched_items,
                "detected_spatial_keywords": matched_spatial,
                "detected_action_verbs": matched_verbs,
                "intent_confidence_scores": confidences,
                "candidate_tool_ranking": ranked_tools,
                "is_uncertain": is_uncertain,
                "original_intent": highest_intent if is_uncertain else None,
                "contributing_factors": contributing_factors
            }
        }
