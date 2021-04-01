terraform {
	required_version = "~> 0.13.05"

	backend "gcs" {
		bucket = "terraform"
		prefix = "trading-infra"
	}
	
  required_providers {
    google = {
      source = "hashicorp/google"
      version = "3.62.0"
    }
  }
}