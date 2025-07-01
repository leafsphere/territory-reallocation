# simulate data for territory reallocation project demo

# US zip code data provided from https://simplemaps.com/data/us-zips
# Pokemon names pulled from https://github.com/lgreski/pokemonData/

################################################################################
# 0. load libraries and data
################################################################################

rm(list = ls() ) # clear workspace
library(stringr)
library(dplyr)
library(ggplot2)

d <- read.csv("data/simplemaps/uszips.csv")

################################################################################
# 1. preprocess zipcode data
################################################################################

# prepad zipcodes with 0's
d <- d %>%
  mutate(zip = str_pad(zip, width = 5, side = "left", pad = "0"))

# remove rows where state_id is 1 of 7: PR, VI, AS, GU, MP, AK, HI
d <- d %>%
  filter(!(state_id %in% c("PR", "VI", "AS", "GU", "MP", "AK", "HI")))

# remove extra columns
d <- d %>%
  select(zip, lat, lng, state_id) %>%
  rename(
    PostalCode = zip,
    Latitude = lat,
    Longitude = lng
  )

################################################################################
# 2. sample 0.5% of zipcode data
################################################################################

# sample 1% of the data stratified by state_id
set.seed(50)
samp <- d %>%
  group_by(state_id) %>%
  sample_frac(0.005) %>%
  ungroup() %>%
  select(-state_id)

# plot zipcode sample to check
ggplot(samp, aes(x = Longitude, y = Latitude)) +
  geom_point() +
  coord_fixed() +
  labs(title = "Sampled Zipcodes") +
  theme_minimal()

# assign territory name (generation/region) based on location
samp <- samp %>%
  mutate(
    TerritoryName = case_when(
      Latitude > 44 & Longitude < -101 ~ "Kanto",
      Latitude <= 44 & Longitude < -112 ~ "Johto",
      Latitude < 43 & Longitude < -101 ~ "Hoenn",
      Latitude > 41 & Longitude < -87 ~ "Sinnoh",
      Latitude > 33 & Longitude < -88 ~ "Unova",
      Latitude <= 33 & Longitude < -91 ~ "Kalos",
      Latitude < 34.5 ~ "Alola",
      Longitude > -77 ~ "Galar",
      TRUE ~ "Paldea"
    )
  )

# plot zipcodes and color by generation to check assignment
ggplot(samp, aes(x = Longitude, y = Latitude, color = TerritoryName)) +
  geom_point() +
  coord_fixed() +
  labs(title = "Sampled Zipcodes by Territory") +
  theme_minimal()

# repeat zipcodes to allow for multiple producers in the same zipcode later
samp <- samp %>%
  slice(rep(1:n(), each = 5)) %>%
  slice_sample(prop = 0.5) # sample 80% of the repeated rows

################################################################################
# 3. Generate territories, producer names, opportunity types, and total assets
################################################################################

# load pokemon data
pkmn <- read.csv("data/pkmndata/Pokemon.csv") %>%
  filter(Form == " ") %>% # remove rows that don't have the Form column empty
  select(Name, Generation)

# assign producer name (Pokemon names) according to territory name
samp <- samp %>%
  mutate(
    ProducerName = case_when(
      TerritoryName == "Kanto" ~ sample(pkmn$Name[pkmn$Generation == 1], n(), replace = T),
      TerritoryName == "Johto" ~ sample(pkmn$Name[pkmn$Generation == 2], n(), replace = T),
      TerritoryName == "Hoenn" ~ sample(pkmn$Name[pkmn$Generation == 3], n(), replace = T),
      TerritoryName == "Sinnoh" ~ sample(pkmn$Name[pkmn$Generation == 4], n(), replace = T),
      TerritoryName == "Unova" ~ sample(pkmn$Name[pkmn$Generation == 5], n(), replace = T),
      TerritoryName == "Kalos" ~ sample(pkmn$Name[pkmn$Generation == 6], n(), replace = T),
      TerritoryName == "Alola" ~ sample(pkmn$Name[pkmn$Generation == 7], n(), replace = T),
      TerritoryName == "Galar" ~ sample(pkmn$Name[pkmn$Generation == 8], n(), replace = T),
      TerritoryName == "Paldea" ~ sample(pkmn$Name[pkmn$Generation == 9], n(), replace = T)
    )
  )

# assign each zipcode with three Opportunity Types
types <- data.frame(
  OpptyType = c("Type A", "Type B", "Type C")
)

samp <- samp %>%
  cross_join(types) %>%
  # randomly sample 80% of the rows
  slice_sample(prop = 0.8)

# generate random values for each Opportunity Type
samp <- samp %>%
  mutate(TotalAssets = floor(runif(n(), min = 1000, max = 10000)))

################################################################################
# 4. output final data
################################################################################

# write final data to csv
write.csv(samp, "assets/sample_data.csv", row.names = FALSE)


