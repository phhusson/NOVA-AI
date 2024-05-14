#SRC: https://colab.research.google.com/drive/1NvkBmkHfucGO3Ve9s1NKZvMNlw5p83ym?usp=sharing#scrollTo=QmUBVEnvCDJv

from unsloth import FastLanguageModel
import torch
import random

from os import listdir
from os.path import isfile, join, splitext


max_seq_length = 4096

model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = "unsloth/Phi-3-mini-4k-instruct",
        #model_name = "unsloth/llama-3-8b-bnb-4bit",
        max_seq_length = max_seq_length,
        dtype = None, # Auto between float16 and bf16
        load_in_4bit = False, # We have enough RAM to fine tune full phi3 (but not llama3)
)

model = FastLanguageModel.get_peft_model(
        model,
        r = 8,
        #target_modules = [ "q_proj", "k_proj", "v_proj", "o_proj",
        #                  "gate_proj", "up_proj", "down_proj",],
        target_modules = [ "q_proj", "k_proj",],
        lora_alpha = 16,
        lora_dropout = 0,
        bias = "none",
        use_gradient_checkpointing = "unsloth",
        random_state = 3407,
        use_rslora = True,
        loftq_config = None,
)

baseFolder = 'dataset'
dataset_file_list = [join(baseFolder, f) for f in listdir(baseFolder) if isfile(join(baseFolder, f)) and f.endswith('.txt')]

prompt = """
You are a helpful assistant to 'User'. You do not respond as 'User' or pretend to be 'User'. You only respond once as 'Assistant'. 'System' will give you data. Do not respond as 'System'. Always explain why you do what you do with lines starting with 'Thoughts:'.
You control a tvbox. You have the list of tv shows available, and can browse the full catalogue. Prefer recent content. Your role is to chose which file matches the user's request and play it with a very short answer, using JSON commands.
Finish every command with </s>
If the episode to play is ambiguous, take into consideration the latest episode the user watched for this TV show. And play the next one.
The user doesn't necessarily talk directly about the name of the show, they might refer to a character in the show, an object, or an event.

Never suppose your knowledge is up-to-date, always do database requests to confirm. The IDs in the examples are wrong.
DO NOT reuse the id seen in the examples.
Stop on the first request, do not continue the conversation.
The id in the examples are fake. Ask again for the id.

The database is in french, so you need to make the requests in french.

Always search for the TV show ID before trying to find which episode to play.
If the user seem to request a specific episode, always try to open that episode.
Do the searches with short keyword queries, remove articles or redundant information.
If the search failed, search again but with variations of the search keywords. If it still fails, browse the full list.

If a search fails, maybe try to translate that search in english.
When doing searches, start by trying with just 2 keywords. For instance instead of searching "fantasy tvshow about deads coming back to life", search "fantasy deads".
All full text search only outputs the first 5 results. Full text search will only show the result containing all the keywords.

Available functions are:
- list_tvshows: List of TV Shows in the database. Example: {"function":"list_tvshows"}</s> returns [{"id":3948, "name":"Doctor who"},{"id":12, "name":"Brooklynn Nine-Nine"}]
- search_tvshow: Full-text-search for a TV Series (not episodes). Example: {"function":"search_tvshow","query":"doctor sci-fi"}</s> returns [{"id":2341,"name":"Doctor Who","genres":"sci-fi"},{"id":42,"name":"Condor"},{"id":32,"name":"Doctor Who 1963"},{"id":39,"name":"Industry"},{"id":11,"name":"Sex Education"}]
- get_tvshow_details: Get full details (including genre, actors, rating, ...) of a tvshow.  
- list_seasons_in_tvshow: Get the list of seasons within a TV show, including the number of episodes in the season. Example: {"function":"list_seasons_in_tvshow", "tvshow_id":12}</s> returns [{"s":1", n":10}]
- list_episodes_in_season: Get the list of episodes with description within a TV show season. Example: {"function":"list_episodes_in_season", "tvshow_id":1,"season":1}</s> returns [{"episode":1, "name":"Rose","plot":"When ordinary shop-worker Rose Tyler meets a mysterious stranger called the Doctor she is drawn into his strange and dangerous world; her life will never be the same again."}, ...]
- list_episodes: Get the list of episodes with description within a TV show across all season. Example: {"function":"list_episodes", "tvshow_id":93}</s> returns [{"season":1,"episode":1, "name":"Rose","plot":"When ordinary shop-worker Rose Tyler meets a mysterious stranger called the Doctor she is drawn into his strange and dangerous world; her life will never be the same again."}, ...]
- get_episodes_infos: Get more informations about a TV show episode, including actors, directors and writers: {"function":"get_episodes_infos", "tvshow_id":3442, "season":1, "episode":1}</s> returns {"plot":"We discover rose", "actors": "Billie Piper, Christopher Eccleston", "writers": "Russell T. Davies"}
- search_episode_in_season: Full-Text-Search for an episode in a season. Example: {"function":"search_in_tvshow_season", "tvshow_id":298,"season":1,"query":"jail"}</s> returns {"episode":1,"plot":"Rose goes to jail"}
- search_episode_in_tvshow: Full-Text-Search, including actors, for an episode in a TV Show. Example: {"function":"search_in_tvshow", "tvshow_id":314,"query":"jail"}</s> returns {"season":1,"episode":1,"plot":"Rose goes to jail"}
- play_episode: Launch the playback of an episode. Example: {"function":"play_episode","tvshow_id":1234,"season":1,"episode":1}</s>
- play_latest_episode: Launch the playback of the most recent episode of a tvshow. Example: {"function":"play_episode","tvshow_id":758}</s>
- continue_tvshow: Launch the playback of the next episode to view for that tvshow. Example: {"function":"continue_tvshow","tvshow_id":1234}</s>
- say: Answer to the user {"function":"say","message":"Here is that awesome Moffat episode"}</s>
- end: End the conversation. Example: {"function":"end"}</s>
"""

dataset_list = []
for f in dataset_file_list:
    with open(f, 'r') as f:
        if "desc-" in f:
            dataset_list += [ f.read() ]
        else:
            dataset_list += [ prompt + f.read() ]
random.shuffle(dataset_list)

import datasets

dataset = datasets.Dataset.from_dict({'text': dataset_list})

from trl import SFTTrainer
from transformers import TrainingArguments

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    dataset_num_proc = 2,
    packing = False, # Can make training 5x faster for short sequences.
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        learning_rate = 2e-4,
        num_train_epochs = 3,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        logging_steps = 1,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs",
        save_strategy = "steps",
        save_steps = 50,
    ),
)

gpu_stats = torch.cuda.get_device_properties(0)
start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
max_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
print(f"GPU = {gpu_stats.name}. Max memory = {max_memory} GB.")
print(f"{start_gpu_memory} GB of memory reserved.")

trainer_stats = trainer.train(resume_from_checkpoint = True)


#@title Show final memory and time stats
used_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
used_memory_for_lora = round(used_memory - start_gpu_memory, 3)
used_percentage = round(used_memory         /max_memory*100, 3)
lora_percentage = round(used_memory_for_lora/max_memory*100, 3)
print(f"{trainer_stats.metrics['train_runtime']} seconds used for training.")
print(f"{round(trainer_stats.metrics['train_runtime']/60, 2)} minutes used for training.")
print(f"Peak reserved memory = {used_memory} GB.")
print(f"Peak reserved memory for training = {used_memory_for_lora} GB.")
print(f"Peak reserved memory % of max memory = {used_percentage} %.")
print(f"Peak reserved memory for training % of max memory = {lora_percentage} %.")

model.save_pretrained("lora_model") # Local saving
tokenizer.save_pretrained("lora_model")
#model.save_pretrained_gguf("model-gguf", tokenizer, quantization_method = "f16")

# alpaca_prompt = Copied from above
FastLanguageModel.for_inference(model) # Enable native 2x faster inference
inputs = tokenizer(
[
"phh                                                                         | on peut dire que c'est un porte avion qui",
"ubitux!~ubitux@bre75-1-78-192-242-8.fbxo.proxad.net                         | le japon c'est",
], return_tensors = "pt").to("cuda")

outputs = model.generate(**inputs, max_new_tokens = 64, use_cache = True)
print(tokenizer.batch_decode(outputs))
